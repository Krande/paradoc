dev:
	mamba env update --file environment.dev.yml --prune

format:
	black --config pyproject.toml . && isort . && ruff . --fix