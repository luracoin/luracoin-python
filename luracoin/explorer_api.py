"""Public, read-only HTTP API for Luracoin block explorers.

This service is deliberately separate from the authenticated operator RPC.
Core lookups read the canonical node stores directly and do not require the
optional SQLite explorer index.  Collection, ranking, and aggregate routes
are available only while that index is enabled and ready.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import re
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence, Tuple

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from luracoin.blocks import Block
from luracoin.chain import Chain
from luracoin.config import Config
from luracoin.wallet import is_valid_address

API_VERSION = 1
API_PREFIX = "/api/v1"
DEFAULT_EXPLORER_HOST = "127.0.0.1"
DEFAULT_EXPLORER_PORT = 18000
DEFAULT_PAGE_SIZE = 25
DEFAULT_BLOCK_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
MAX_BLOCK_PAGE_SIZE = 10
MAX_PAGE_OFFSET = 2_147_483_647

_HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_MONETARY_FIELDS = {
    "amount",
    "balance",
    "block_reward",
    "circulating_supply",
    "fee",
    "fees",
    "received",
    "reward",
    "sent",
    "spendable_balance",
    "supply",
    "total_fees",
    "total_received",
    "total_rewards",
    "total_sent",
    "total_supply",
    "total_transferred",
    "value",
    "volume",
}

_INDEX_METHODS = {
    "transactions": (
        "list_transactions",
        "get_transactions",
        "query_transactions",
    ),
    "addresses": (
        "list_addresses",
        "get_addresses",
        "top_addresses",
        "rank_addresses",
    ),
    "address_transactions": (
        "get_address_transactions",
        "list_address_transactions",
        "address_transactions",
    ),
    "stats": ("get_stats", "stats", "statistics"),
}

log = logging.getLogger(__name__)


class IndexState(BaseModel):
    enabled: bool
    ready: bool
    state: str
    indexed_height: Optional[int] = None
    target_height: Optional[int] = None
    progress: Optional[float] = None


class Pagination(BaseModel):
    limit: int
    offset: int
    count: int
    total: Optional[int] = None


class BlockPagination(Pagination):
    before_height: Optional[int] = None
    next_before_height: Optional[int] = None


class ExplorerTransaction(BaseModel):
    id: str
    chain: int
    nonce: int
    fee: str
    value: str
    from_address: str
    to_address: str
    unlock_sig: Optional[str] = None
    block_height: int
    block_id: str
    block_timestamp: int
    transaction_index: int
    confirmations: int
    is_coinbase: Optional[bool] = None
    direction: Optional[str] = None


class BlockSummary(BaseModel):
    height: int
    prev_block_hash: str
    miner: str
    id: str
    nonce: int
    version: int
    timestamp: int
    bits: str
    transaction_count: int
    size_bytes: int
    total_fees: str
    reward: str
    confirmations: int


class AddressSummary(BaseModel):
    address: str
    balance: str
    nonce: int
    total_received: str
    total_sent: str
    total_fees: str
    transaction_count: int
    first_seen_height: int
    last_seen_height: int


class HealthResponse(BaseModel):
    ok: bool
    network: str
    chain_id: int
    api_version: int


class CapabilityState(BaseModel):
    block_list: bool
    block_lookup: bool
    block_transactions: bool
    transaction_lookup: bool
    address_state: bool
    transaction_feed: bool
    address_ranking: bool
    address_history: bool
    aggregate_stats: bool


class StatusResponse(BaseModel):
    network: str
    chain_id: int
    api_version: int
    initialized: bool
    height: int
    tip_id: Optional[str] = None
    ready: bool
    syncing: bool
    index: IndexState
    capabilities: CapabilityState


class FeatureAvailability(BaseModel):
    enabled: bool
    ready: bool


class FeatureSet(BaseModel):
    core: FeatureAvailability
    explorer_index: IndexState


class FeaturesResponse(BaseModel):
    api_version: int
    features: FeatureSet


class BlockPageResponse(BaseModel):
    network: str
    items: list[BlockSummary]
    pagination: BlockPagination


class BlockResponse(BaseModel):
    network: str
    block: BlockSummary


class BlockReference(BaseModel):
    height: int
    id: str


class BlockTransactionsResponse(BaseModel):
    network: str
    block: BlockReference
    items: list[ExplorerTransaction]
    pagination: Pagination


class TransactionPageResponse(BaseModel):
    network: str
    items: list[ExplorerTransaction]
    pagination: Pagination


class TransactionResponse(BaseModel):
    network: str
    transaction: ExplorerTransaction


class AddressPageResponse(BaseModel):
    network: str
    items: list[AddressSummary]
    pagination: Pagination


class AddressTransactionsResponse(BaseModel):
    network: str
    address: str
    items: list[ExplorerTransaction]
    pagination: Pagination


class AddressResponse(BaseModel):
    network: str
    address: str
    exists: bool
    balance: str
    nonce: int


class ExplorerStats(BaseModel):
    network: str
    chain_id: int
    indexed_height: int
    indexed_block_id: Optional[str] = None
    blocks: int
    transactions: int
    addresses: int
    total_fees: str
    total_transferred: str
    total_rewards: str


class StatsResponse(BaseModel):
    network: str
    stats: ExplorerStats


class _ApiProblem(Exception):
    """An intentional, JSON-safe public API error."""

    def __init__(
        self,
        status_code: int,
        error: str,
        *,
        extra: Optional[dict] = None,
    ) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.extra = extra or {}


def _chain_for(node: Any = None) -> Chain:
    chain = getattr(node, "chain", None)
    return chain if chain is not None else Chain()


def _json_safe(value: Any, *, field: Optional[str] = None) -> Any:
    """Return JSON-compatible data and stringify known monetary uint64s."""

    if (
        field in _MONETARY_FIELDS
        and isinstance(value, int)
        and not isinstance(value, bool)
    ):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item, field=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, bytes):
        return value.hex()
    enum_value = getattr(value, "value", value)
    if enum_value is not value:
        return _json_safe(enum_value, field=field)
    return value


def _transaction_payload(
    transaction: Any,
    *,
    block_height: Optional[int] = None,
    block_id: Optional[str] = None,
    block_timestamp: Optional[int] = None,
    transaction_index: Optional[int] = None,
    confirmations: Optional[int] = None,
) -> dict:
    payload = dict(transaction.json())
    payload.update(
        {
            "block_height": block_height,
            "block_id": block_id,
            "block_timestamp": block_timestamp,
            "transaction_index": transaction_index,
            "confirmations": confirmations,
        }
    )
    return _json_safe(payload)


def _block_summary_payload(
    block: Any, *, chain_height: Optional[int] = None
) -> dict:
    header = getattr(block, "header", None)
    if callable(header):
        payload = dict(header())
    else:
        payload = dict(block.json())
        payload.pop("txns", None)
    # Transactions have a fixed canonical length, so a list view does not
    # need to reserialize (and rehash) the entire block just to report size.
    size_bytes = 118 + len(block.txns) * Config.TRANSACTION_LENGTH
    total_fees = 0
    reward = 0
    for transaction in block.txns:
        if bool(getattr(transaction, "is_coinbase", False)):
            reward += int(transaction.value)
        else:
            total_fees += int(transaction.fee)
    payload["transaction_count"] = len(block.txns)
    payload["size_bytes"] = size_bytes
    payload["total_fees"] = total_fees
    payload["reward"] = reward
    payload["confirmations"] = (
        max(0, chain_height - block.height + 1)
        if chain_height is not None
        else None
    )
    return _json_safe(payload)


def _canonical_height(chain: Chain) -> Optional[int]:
    initialized = chain.get_block_file_number(0) is not None
    return chain.tip if initialized else None


def _core_block_page(
    chain: Chain,
    *,
    limit: int,
    offset: int,
    before_height: Optional[int],
) -> dict:
    chain_height = _canonical_height(chain)
    if chain_height is None:
        return {
            "items": [],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": 0,
                "total": 0,
                "before_height": before_height,
                "next_before_height": None,
            },
        }

    anchor = chain_height
    if before_height is not None:
        anchor = min(anchor, before_height - 1)
    start = anchor - offset
    heights = (
        list(range(start, max(-1, start - limit), -1)) if start >= 0 else []
    )
    items = []
    for height in heights:
        # Load and discard one block at a time.  A protocol-valid block may be
        # 8 MiB and contain tens of thousands of transactions; materializing a
        # whole page of full blocks lets one request amplify memory usage.
        block = Block.get(height)
        if block is not None:
            items.append(
                _block_summary_payload(block, chain_height=chain_height)
            )
    next_before_height = None
    if items:
        lowest_height = min(int(item["height"]) for item in items)
        if lowest_height > 0:
            next_before_height = lowest_height
    return {
        "items": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(items),
            "total": chain_height + 1,
            "before_height": before_height,
            "next_before_height": next_before_height,
        },
    }


def _parse_transaction_location(location: Any) -> Optional[Tuple[int, int]]:
    if location is None:
        return None
    if isinstance(location, dict):
        height = location.get("height", location.get("block_height"))
        index = location.get(
            "index",
            location.get("transaction_index", location.get("tx_index")),
        )
    elif isinstance(location, (list, tuple)) and len(location) >= 2:
        height, index = location[:2]
    else:
        return None
    if (
        not isinstance(height, int)
        or isinstance(height, bool)
        or not isinstance(index, int)
        or isinstance(index, bool)
        or height < 0
        or index < 0
    ):
        return None
    return height, index


def _resolve_block(chain: Chain, block_ref: str) -> Optional[Any]:
    if block_ref.isdecimal():
        height = int(block_ref)
        if height > 0xFFFFFFFF:
            raise _ApiProblem(400, "invalid_block_reference")
    elif _HASH_PATTERN.fullmatch(block_ref):
        height = chain.get_block_height(block_ref.lower())
        if height is None:
            return None
    else:
        raise _ApiProblem(400, "invalid_block_reference")
    return Block.get(height)


def _resolve_transaction(chain: Chain, transaction_id: str) -> Optional[dict]:
    lookup = getattr(chain, "get_transaction_location", None)
    if not callable(lookup):
        return None
    parsed = _parse_transaction_location(lookup(transaction_id))
    if parsed is None:
        return None
    height, index = parsed
    block = Block.get(height)
    if block is None or index >= len(block.txns):
        return None
    transaction = block.txns[index]
    if transaction.id.lower() != transaction_id:
        return None
    initialized = chain.get_block_file_number(0) is not None
    chain_height = chain.tip if initialized else None
    confirmations = (
        max(0, chain_height - height + 1) if chain_height is not None else None
    )
    return _transaction_payload(
        transaction,
        block_height=height,
        block_id=block.id,
        block_timestamp=block.timestamp,
        transaction_index=index,
        confirmations=confirmations,
    )


async def _status_value(indexer: Any) -> Any:
    status = getattr(indexer, "status", None)
    if callable(status):
        if inspect.iscoroutinefunction(status):
            return await status()
        result = await asyncio.to_thread(status)
        return await result if inspect.isawaitable(result) else result
    if status is not None:
        return status
    state = getattr(indexer, "state", None)
    if callable(state):
        if inspect.iscoroutinefunction(state):
            return await state()
        result = await asyncio.to_thread(state)
        return await result if inspect.isawaitable(result) else result
    return state


def _safe_progress(raw: dict) -> dict:
    nested = raw.get("progress")
    if isinstance(nested, dict):
        raw = {**nested, **raw}
    progress = {}
    field_aliases = {
        "indexed_height": ("indexed_height", "last_indexed_height"),
        "target_height": ("target_height", "chain_height", "tip_height"),
        "progress": ("progress", "percent", "percentage"),
    }
    for public_name, aliases in field_aliases.items():
        for alias in aliases:
            value = raw.get(alias)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                progress[public_name] = value
                break
    return progress


async def _derived_index_status(index: Any, indexer: Any) -> dict:
    """Derive status for indexers that predate a public status method."""

    metadata = {}
    getter = getattr(index, "get_metadata", None)
    if callable(getter):
        try:
            if inspect.iscoroutinefunction(getter):
                result = await getter()
            else:
                result = await asyncio.to_thread(getter)
                if inspect.isawaitable(result):
                    result = await result
            if isinstance(result, dict):
                metadata = result
        except Exception:
            log.exception("Unable to read explorer index metadata")
            return {"state": "error", "ready": False}

    indexed_height = metadata.get("indexed_height")
    if not isinstance(indexed_height, int) or isinstance(indexed_height, bool):
        indexed_height = None

    target_height = None
    chain = getattr(indexer, "chain", None)
    if chain is not None:
        try:
            height = await asyncio.to_thread(_canonical_height, chain)
            target_height = -1 if height is None else height
        except Exception:
            log.exception("Unable to read canonical height for explorer index")

    result = {
        "state": "building",
        "ready": False,
    }
    if indexed_height is not None:
        result["indexed_height"] = indexed_height
    if target_height is not None:
        result["target_height"] = target_height
    if indexed_height is not None and target_height is not None:
        ready = indexed_height >= target_height
        result["state"] = "ready" if ready else "building"
        result["ready"] = ready
        if target_height < 0:
            result["progress"] = 100.0
        else:
            result["progress"] = round(
                max(
                    0.0,
                    min(
                        100.0,
                        (indexed_height + 1) * 100 / (target_height + 1),
                    ),
                ),
                2,
            )

    if getattr(indexer, "last_error", None) is not None:
        result["state"] = "error"
        result["ready"] = False
    return result


async def _index_state(index: Any, indexer: Any) -> dict:
    if index is None:
        return {"enabled": False, "ready": False, "state": "disabled"}
    if indexer is None:
        return {"enabled": True, "ready": True, "state": "ready"}

    try:
        raw = await _status_value(indexer)
    except Exception:
        log.exception("Unable to read explorer indexer status")
        return {"enabled": True, "ready": False, "state": "error"}

    if raw is None:
        raw = await _derived_index_status(index, indexer)

    if isinstance(raw, dict):
        raw_state = raw.get("state", raw.get("status", "unknown"))
        state = str(getattr(raw_state, "value", raw_state)).lower()
        ready_value = raw.get("ready")
        progress = _safe_progress(raw)
    else:
        raw_state = getattr(raw, "value", raw)
        state = str(raw_state or "unknown").lower()
        ready_value = getattr(indexer, "ready", None)
        progress = {}

    if isinstance(ready_value, bool):
        ready = ready_value
    elif (
        "indexed_height" in progress
        and "target_height" in progress
        and progress["indexed_height"] >= progress["target_height"]
    ):
        ready = True
    else:
        ready = state in {"complete", "completed", "idle", "ready", "synced"}

    if state in {"failed", "failure", "faulted"}:
        state = "error"
        ready = False
    elif not ready and state in {"running", "starting", "unknown"}:
        state = "building"
    elif ready:
        state = "ready"

    return {"enabled": True, "ready": ready, "state": state, **progress}


async def _ready_index(index: Any, indexer: Any) -> Any:
    state = await _index_state(index, indexer)
    if not state["enabled"]:
        raise _ApiProblem(
            503,
            "explorer_index_disabled",
            extra={"index": state},
        )
    if not state["ready"]:
        error = (
            "explorer_index_error"
            if state["state"] == "error"
            else "explorer_index_building"
        )
        raise _ApiProblem(503, error, extra={"index": state})
    return index


def _filtered_keyword_arguments(method: Any, values: dict) -> dict:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return values
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return values
    return {
        key: value
        for key, value in values.items()
        if key in signature.parameters
    }


async def _call_index(
    index: Any,
    operation: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    method = None
    for name in _INDEX_METHODS[operation]:
        candidate = getattr(index, name, None)
        if callable(candidate):
            method = candidate
            break
        if candidate is not None and not args and not kwargs:
            return candidate
    if method is None:
        raise RuntimeError(
            "ExplorerIndex does not implement the %s operation" % operation
        )

    accepted_kwargs = _filtered_keyword_arguments(method, kwargs)
    if inspect.iscoroutinefunction(method):
        return await method(*args, **accepted_kwargs)
    result = await asyncio.to_thread(method, *args, **accepted_kwargs)
    return await result if inspect.isawaitable(result) else result


def _normalise_page(
    result: Any,
    *,
    item_keys: Sequence[str],
    limit: int,
    offset: int,
) -> dict:
    total = None
    if isinstance(result, dict):
        items = None
        for key in ("items", "results", "rows", *item_keys):
            if key in result:
                items = result[key]
                break
        if items is None:
            items = []
        total = result.get("total", result.get("total_count"))
    elif (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[0], (list, tuple))
    ):
        items, total = result
    elif isinstance(result, (list, tuple)):
        items = result
    else:
        raise ValueError("ExplorerIndex returned an invalid page")

    items = list(items)
    pagination = {
        "limit": limit,
        "offset": offset,
        "count": len(items),
    }
    if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
        pagination["total"] = total
    return {"items": _json_safe(items), "pagination": pagination}


def create_explorer_app(
    node: Any = None,
    index: Any = None,
    indexer: Any = None,
) -> FastAPI:
    """Create the public explorer ASGI application.

    ``index`` is expected to expose ``list_transactions``, ``list_addresses``,
    ``get_address_transactions``, and ``get_stats``.  A few conservative
    aliases are accepted by the adapter above.  List methods receive bounded
    ``limit`` and ``offset`` keyword arguments.
    """

    app = FastAPI(
        title="Luracoin Explorer API",
        version=str(API_VERSION),
        description=(
            "Public, read-only access to canonical Luracoin chain data. "
            "Global transaction feeds, address histories, rankings, and "
            "aggregate routes require the optional explorer index."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        contact={"name": "Luracoin"},
        license_info={"name": "MIT"},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
        max_age=600,
    )

    @app.exception_handler(_ApiProblem)
    async def api_problem_handler(
        _request: Request, problem: _ApiProblem
    ) -> JSONResponse:
        return JSONResponse(
            status_code=problem.status_code,
            content={"error": problem.error, **problem.extra},
        )

    @app.get(
        "/health",
        tags=["service"],
        summary="Service health",
        response_model=HealthResponse,
    )
    async def health() -> dict:
        return {
            "ok": True,
            "network": Config.NETWORK,
            "chain_id": Config.CHAIN_ID,
            "api_version": API_VERSION,
        }

    @app.get(
        f"{API_PREFIX}/status",
        tags=["service"],
        summary="Canonical chain status",
        response_model=StatusResponse,
        response_model_exclude_none=True,
    )
    async def status() -> dict:
        chain = _chain_for(node)

        def read_status() -> Tuple[bool, int, Optional[str]]:
            initialized = chain.get_block_file_number(0) is not None
            if not initialized:
                return False, -1, None
            height = chain.tip
            tip_block = Block.get(height)
            tip_id = tip_block.id if tip_block is not None else None
            return True, height, tip_id

        initialized, height, tip_id = await asyncio.to_thread(read_status)
        index_state = await _index_state(index, indexer)
        return {
            "network": Config.NETWORK,
            "chain_id": Config.CHAIN_ID,
            "api_version": API_VERSION,
            "initialized": initialized,
            "height": height,
            "tip_id": tip_id,
            "ready": bool(getattr(node, "ready", initialized)),
            "syncing": bool(getattr(node, "syncing", False)),
            "index": index_state,
            "capabilities": {
                "block_list": True,
                "block_lookup": True,
                "block_transactions": True,
                "transaction_lookup": True,
                "address_state": True,
                "transaction_feed": index_state["ready"],
                "address_ranking": index_state["ready"],
                "address_history": index_state["ready"],
                "aggregate_stats": index_state["ready"],
            },
        }

    @app.get(
        f"{API_PREFIX}/features",
        tags=["service"],
        summary="API feature availability",
        response_model=FeaturesResponse,
        response_model_exclude_none=True,
    )
    async def features() -> dict:
        return {
            "api_version": API_VERSION,
            "features": {
                "core": {"enabled": True, "ready": True},
                "explorer_index": await _index_state(index, indexer),
            },
        }

    @app.get(
        f"{API_PREFIX}/blocks",
        tags=["core"],
        summary="List canonical blocks newest first",
        response_model=BlockPageResponse,
    )
    async def list_blocks(
        limit: int = Query(
            DEFAULT_BLOCK_PAGE_SIZE, ge=1, le=MAX_BLOCK_PAGE_SIZE
        ),
        offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
        before_height: Optional[int] = Query(None, ge=0, le=0xFFFFFFFF),
    ) -> dict:
        page = await asyncio.to_thread(
            _core_block_page,
            _chain_for(node),
            limit=limit,
            offset=offset,
            before_height=before_height,
        )
        return {"network": Config.NETWORK, **page}

    @app.get(
        f"{API_PREFIX}/blocks/{{block_ref}}",
        tags=["core"],
        summary="Get a block by height or hash",
        response_model=BlockResponse,
    )
    async def get_block(block_ref: str) -> dict:
        chain = _chain_for(node)
        block, chain_height = await asyncio.to_thread(
            lambda: (
                _resolve_block(chain, block_ref),
                _canonical_height(chain),
            )
        )
        if block is None:
            raise _ApiProblem(404, "block_not_found")
        return {
            "network": Config.NETWORK,
            "block": _block_summary_payload(block, chain_height=chain_height),
        }

    @app.get(
        f"{API_PREFIX}/blocks/{{block_ref}}/transactions",
        tags=["core"],
        summary="List a block's transactions",
        response_model=BlockTransactionsResponse,
        response_model_exclude_none=True,
    )
    async def list_block_transactions(
        block_ref: str,
        limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
    ) -> dict:
        chain = _chain_for(node)
        block, chain_height = await asyncio.to_thread(
            lambda: (
                _resolve_block(chain, block_ref),
                _canonical_height(chain),
            )
        )
        if block is None:
            raise _ApiProblem(404, "block_not_found")
        transactions = [
            _transaction_payload(
                transaction,
                block_height=block.height,
                block_id=block.id,
                block_timestamp=block.timestamp,
                transaction_index=transaction_index,
                confirmations=(
                    max(0, chain_height - block.height + 1)
                    if chain_height is not None
                    else None
                ),
            )
            for transaction_index, transaction in enumerate(
                block.txns[offset : offset + limit], start=offset
            )
        ]
        return {
            "network": Config.NETWORK,
            "block": {"height": block.height, "id": block.id},
            "items": transactions,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(transactions),
                "total": len(block.txns),
            },
        }

    @app.get(
        f"{API_PREFIX}/transactions",
        tags=["indexed"],
        summary="List indexed transactions",
        response_model=TransactionPageResponse,
        response_model_exclude_none=True,
    )
    async def list_transactions(
        limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
    ) -> dict:
        ready = await _ready_index(index, indexer)
        try:
            result = await _call_index(
                ready, "transactions", limit=limit, offset=offset
            )
            page = _normalise_page(
                result,
                item_keys=("transactions",),
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            log.exception("Explorer transaction listing failed")
            raise _ApiProblem(503, "explorer_index_unavailable") from exc
        return {"network": Config.NETWORK, **page}

    @app.get(
        f"{API_PREFIX}/transactions/{{txid}}",
        tags=["core"],
        summary="Get a confirmed transaction by ID",
        response_model=TransactionResponse,
        response_model_exclude_none=True,
    )
    async def get_transaction(txid: str) -> dict:
        if not _HASH_PATTERN.fullmatch(txid):
            raise _ApiProblem(400, "invalid_transaction_id")
        txid = txid.lower()
        transaction = await asyncio.to_thread(
            _resolve_transaction,
            _chain_for(node),
            txid,
        )
        if transaction is None:
            raise _ApiProblem(404, "transaction_not_found")
        return {"network": Config.NETWORK, "transaction": transaction}

    @app.get(
        f"{API_PREFIX}/addresses",
        tags=["indexed"],
        summary="Rank indexed addresses",
        response_model=AddressPageResponse,
    )
    async def list_addresses(
        limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
    ) -> dict:
        ready = await _ready_index(index, indexer)
        try:
            result = await _call_index(
                ready, "addresses", limit=limit, offset=offset
            )
            page = _normalise_page(
                result,
                item_keys=("addresses",),
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            log.exception("Explorer address ranking failed")
            raise _ApiProblem(503, "explorer_index_unavailable") from exc
        return {"network": Config.NETWORK, **page}

    @app.get(
        f"{API_PREFIX}/addresses/{{address}}/transactions",
        tags=["indexed"],
        summary="List an address's indexed transactions",
        response_model=AddressTransactionsResponse,
        response_model_exclude_none=True,
    )
    async def list_address_transactions(
        address: str,
        limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        offset: int = Query(0, ge=0, le=MAX_PAGE_OFFSET),
    ) -> dict:
        if not is_valid_address(address):
            raise _ApiProblem(400, "invalid_address")
        ready = await _ready_index(index, indexer)
        try:
            result = await _call_index(
                ready,
                "address_transactions",
                address,
                limit=limit,
                offset=offset,
            )
            page = _normalise_page(
                result,
                item_keys=("transactions",),
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            log.exception("Explorer address history failed")
            raise _ApiProblem(503, "explorer_index_unavailable") from exc
        return {"network": Config.NETWORK, "address": address, **page}

    @app.get(
        f"{API_PREFIX}/addresses/{{address}}",
        tags=["core"],
        summary="Get canonical address state",
        response_model=AddressResponse,
    )
    async def get_address(address: str) -> dict:
        if not is_valid_address(address):
            raise _ApiProblem(400, "invalid_address")
        account = await asyncio.to_thread(
            _chain_for(node).get_account, address
        )
        exists = account is not None
        account = account or {"balance": 0, "nonce": 0}
        return {
            "network": Config.NETWORK,
            "address": address,
            "exists": exists,
            "balance": str(account["balance"]),
            "nonce": account["nonce"],
        }

    @app.get(
        f"{API_PREFIX}/stats",
        tags=["indexed"],
        summary="Get indexed chain aggregates",
        response_model=StatsResponse,
        response_model_exclude_none=True,
    )
    async def get_stats() -> dict:
        ready = await _ready_index(index, indexer)
        try:
            result = await _call_index(ready, "stats")
            if not isinstance(result, dict):
                raise ValueError("ExplorerIndex returned invalid statistics")
        except Exception as exc:
            log.exception("Explorer statistics lookup failed")
            raise _ApiProblem(503, "explorer_index_unavailable") from exc
        return {"network": Config.NETWORK, "stats": _json_safe(result)}

    return app


class _EmbeddedUvicornServer(uvicorn.Server):
    """Uvicorn server variant that never installs process signal handlers."""

    def install_signal_handlers(self) -> None:
        # Compatibility with Uvicorn releases that call this hook directly.
        return None

    @contextlib.contextmanager
    def capture_signals(self) -> Iterable[None]:
        # Newer Uvicorn releases wrap ``serve`` in this context manager.
        yield


async def _call_lifecycle(target: Any, method_name: str) -> None:
    method = getattr(target, method_name, None)
    if not callable(method):
        return
    if inspect.iscoroutinefunction(method):
        await method()
        return
    result = await asyncio.to_thread(method)
    if inspect.isawaitable(result):
        await result


class ExplorerApiServer:
    """Embed the public explorer API in the node's existing asyncio loop."""

    def __init__(
        self,
        node: Any = None,
        host: str = DEFAULT_EXPLORER_HOST,
        port: int = DEFAULT_EXPLORER_PORT,
        index_enabled: bool = False,
        index_path: Optional[str] = None,
        poll_interval: float = 2.0,
    ) -> None:
        if not isinstance(host, str) or not host.strip():
            raise ValueError("Explorer API host must be non-empty")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise ValueError("Explorer API port must be between 1 and 65535")
        if poll_interval <= 0:
            raise ValueError("Explorer index poll interval must be positive")

        self.node = node
        self.host = host
        self.port = port
        self.index_enabled = bool(index_enabled)
        self.index_path = index_path
        self.poll_interval = float(poll_interval)

        self.index = None
        self.indexer = None
        self.app = create_explorer_app(node=node)
        self._server = None
        self._serve_task = None
        self._lock = asyncio.Lock()

    @property
    def started(self) -> bool:
        return bool(
            self._server is not None
            and self._serve_task is not None
            and not self._serve_task.done()
            and self._server.started
        )

    def _resolved_index_path(self) -> str:
        if self.index_path:
            return str(Path(self.index_path).expanduser().resolve())
        for name in (
            "EXPLORER_INDEX_PATH",
            "EXPLORER_DATABASE_PATH",
            "EXPLORER_DB_PATH",
        ):
            configured = getattr(Config, name, None)
            if configured:
                return str(Path(configured).expanduser().resolve())
        return str((Path(Config.DATA_DIR) / "explorer.sqlite3").resolve())

    async def _prepare_index(self) -> None:
        if not self.index_enabled or self.index is not None:
            return
        # Keeping this import inside the enabled branch ensures ordinary full
        # nodes never import or instantiate the optional SQLite machinery.
        from luracoin.explorer_index import ExplorerIndex, ExplorerIndexer

        self.index = ExplorerIndex(
            self._resolved_index_path(),
            network=Config.NETWORK,
            chain_id=Config.CHAIN_ID,
        )
        await _call_lifecycle(self.index, "initialize")
        self.indexer = ExplorerIndexer(
            self.index,
            chain=_chain_for(self.node),
            block_cls=Block,
            poll_interval=self.poll_interval,
        )
        self.app = create_explorer_app(
            node=self.node,
            index=self.index,
            indexer=self.indexer,
        )

    async def start(self) -> None:
        async with self._lock:
            if self.started:
                return
            try:
                await self._stop_uvicorn()
                await self._prepare_index()
                if self.indexer is not None:
                    await _call_lifecycle(self.indexer, "start")
                config = uvicorn.Config(
                    self.app,
                    host=self.host,
                    port=self.port,
                    log_level="info",
                    access_log=False,
                    lifespan="on",
                )
                self._server = _EmbeddedUvicornServer(config)
                self._serve_task = asyncio.create_task(
                    self._server.serve(),
                    name="luracoin-explorer-api",
                )
                await self._wait_until_started()
            except BaseException:
                await self._stop_uvicorn()
                await self._teardown_index()
                raise

    async def _wait_until_started(self, timeout: float = 10.0) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while self._server is not None and not self._server.started:
            if self._serve_task is None:
                raise RuntimeError("Explorer API did not create a serve task")
            if self._serve_task.done():
                try:
                    self._serve_task.result()
                except SystemExit as exc:
                    raise RuntimeError("Explorer API failed to bind") from exc
                raise RuntimeError("Explorer API stopped during startup")
            if loop.time() >= deadline:
                raise TimeoutError("Explorer API startup timed out")
            await asyncio.sleep(0.01)

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_uvicorn()
            await self._teardown_index()

    async def _teardown_index(self) -> None:
        if self.indexer is not None:
            with contextlib.suppress(Exception):
                await _call_lifecycle(self.indexer, "stop")
        if self.index is not None:
            with contextlib.suppress(Exception):
                await _call_lifecycle(self.index, "close")
        if self.index_enabled:
            self.indexer = None
            self.index = None
            self.app = create_explorer_app(node=self.node)

    async def _stop_uvicorn(self) -> None:
        server = self._server
        task = self._serve_task
        self._server = None
        self._serve_task = None
        if task is None:
            return
        if server is not None:
            server.should_exit = True
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
        except asyncio.TimeoutError:
            if server is not None:
                server.force_exit = True
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        except (asyncio.CancelledError, SystemExit):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except Exception:
            # Uvicorn has already stopped; retain the original failure in logs
            # without making repeated cleanup calls fail.
            log.exception("Explorer API serve task stopped with an error")
