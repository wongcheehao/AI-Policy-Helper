.PHONY: dev test fmt fix
dev:
	docker compose up --build

test:
	docker compose run --rm backend python -m pytest -q

fmt:
	docker compose run --rm backend black app

fix:
	@echo "Starting code linting with auto-fix!"
	@if [ ! -d .venv ]; then python3 -m venv .venv; fi
	@. .venv/bin/activate && python -m ensurepip --upgrade && python -m pip install -q --upgrade pip && python -m pip install -q ruff && ruff check . --fix

# Create a virtual environment using uv and install dependencies (macOS version)
create-venv-macos:
	@if ! command -v brew >/dev/null 2>&1; then \
		echo "$(COLOR_BLUE)Homebrew not found. Installing Homebrew...$(COLOR_RESET)"; \
		/bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; \
	fi
	@brew install uv
	@uv venv --python 3.11 .venv
	@. .venv/bin/activate && uv pip install -r backend/requirements.txt