# Interop Registry

## Local Application Setup
- Install Docker and Docker Compose.
- Copy the root environment template and adjust credentials if needed:
  ```bash
  cp .env.example .env
  ```
- Start the stack from the repository root:
  ```bash
  docker compose up --build
  ```
  The Flask application listens on `http://localhost:50505`, PostgreSQL on `localhost:5433`.

## Interop Utilities Script
- Copy the script-specific environment file:
  ```bash
  cp scripts/.env.example scripts/.env
  ```
- Create a dedicated virtual environment for the script utilities:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```
- Install the script dependencies:
  ```bash
  python -m pip install -r scripts/requirements.txt
  ```
- Run utilities from the repository root:
  ```bash
  python scripts/interop_utils.py --list
  python scripts/interop_utils.py --ingest-bulk
  ```
  The `--list` flag prints the current registry contents. `--ingest-bulk` ingests all gene and strain entities using the configuration defined in `scripts/.env`.

## REST API
- `GET /<resource>/<local_id_or_uid>`  
  Returns the registry entry for a gene or strain using either its local identifier or UID. Valid resources are `gene` and `strain`.
- `GET /pair/<gene_id,strain_id>`  
  Retrieves the combined interoperability payload for a specific gene/strain pair.
- `GET /`  
  Renders the HTML dashboard summarizing recent mappings and search results.
