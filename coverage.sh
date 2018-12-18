PYTEST=$(which pytest)
ROOT_DIR=$(git rev-parse --show-toplevel)

coverage run --omit *client.py --source=luracoin -- ${PYTEST} -v ${ROOT_DIR} ${@}
coverage html -d artifacts
coverage report -m --fail-under=90
