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

### Initialize the database schema
- If your tables were dropped or you are starting fresh, you can (re)create the schema and seed lookup rows with:
  ```bash
  python scripts/interop_utils.py --init-db
  ```
  This command creates all tables and seeds the `entity` table (`gene`, `strain`) and the `source_db` table (`Bigg`, `ALEdb`, `PMKbase`, `Pankb`). It is idempotent and safe to run multiple times.

## FAQ
- How does ingest work?
  - `scripts/utils/ingest.py` reads an `entities` list and upserts rows into `registry` and `mapping`, generating stable UIDs (`G-` for genes, `S-` for strains). It deduplicates per `(source_db, entity_type, local_id)` and writes to `audit_log`.
- How are synonyms added for NCBI assemblies (sequence IDs)?
  - For ALEdb strains, ingest calls `fetch_ncbi_assemblies` in `scripts/utils/ncbi_assemblies.py` and stores returned assembly accessions as synonyms for the strain’s UID.
- How are synonyms added for NCBI Gene and UniProt?
  - When an entity includes both `gene_id` and `strain_id`, ingest calls `fetch_ncbi_gene_synonyms` and `fetch_uniprot_id` (see `scripts/utils/ncbi_assemblies.py` and `scripts/utils/uniprot.py`). New values are inserted into `synonyms` and logged as “Added synonym …”.
- Will existing synonyms be logged again?
  - No. Existing (uid, synonym) pairs are skipped to keep inserts and audit entries idempotent.
- Can I remove specific synonyms later?
  - Yes. Use cleanup with a `synonyms` section to remove targeted (uid, synonym) pairs. See `scripts/examples/example_cleanup.json` and `scripts/utils/cleanup.py`.

## Running Tests
- Run all backend tests:
  ```bash
  python3 -m pytest src/backend/tests
  ```
  Ensure your `.env` points to a reachable Postgres if tests touch the DB.

## REST API
- `GET /<resource>/<local_id_or_uid>`  
  Returns the registry entry for a gene or strain using either its local identifier or UID. Valid resources are `gene` and `strain`.
- `GET /pair/<gene_id,strain_id>`  
  Retrieves the combined interoperability payload for a specific gene/strain pair.
- `GET /`  
  Renders the HTML dashboard summarizing recent mappings and search results.

## Backend Docs (Sphinx/Read the Docs style)
Generate and view the auto-documented backend API reference:
- Install dev deps (includes Sphinx): `pip install -r requirements-dev.txt`
- Build HTML docs: `make -C docs html`
- Open `docs/_build/html/index.html` in a browser to view

## Azure Deployment (azd)
- Log in: `azd login`
- Deploy: `azd up`
- When prompted, select resource group `rg-recon-dbinterop`.
- The terminal shows a deployment status link; follow it to track success/failure.
- After code changes, rerun `azd up` to redeploy.
