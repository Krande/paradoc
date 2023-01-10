dev:
	mamba env update --file environment.dev.yml --prune

format:
	black . && isort . && flake8 .