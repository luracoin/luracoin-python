PYTEST=$(which pytest)
ROOT_DIR=$(git rev-parse --show-toplevel)

coverage run --source=luracoin -- ${PYTEST} -v ${ROOT_DIR} ${@} --ignore=venv/
coverage html -d artifacts
coverage report -m --fail-under=88
