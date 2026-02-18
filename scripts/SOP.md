# Standard Operating Procedure: Registry Scripts

This SOP covers repeatable operations for loading, inspecting, and cleaning registry data using the Python utilities under `scripts/`.

## Scope and responsibilities
- Owners: data platform team; operators follow this runbook for routine loads and cleanups.
- Systems touched: PostgreSQL registry DB (Azure or local), Azure Key Vault when `CONNECTION_MODE=azure`.
- Safety: write operations use SQLAlchemy transactions; failed batches are rolled back before continuing. The `--cleanup-all` flow is destructive.

## Pre-run checklist
- Python 3.11+ available; dependencies installed with `pip install -r requirements.txt` from `scripts/`.
- Environment configured in `scripts/.env`:
  - `CONNECTION_MODE` set to `azure` or `local`.
  - For Azure: `DB_HOST`, `DB_NAME`, `DB_USERNAME`, `KEYVAULT_NAME`, `KEYVAULT_SECRET_NAME` set and your identity has Key Vault and DB access.
  - For local: `LOCAL_DB_*` values populated.
- Network reachability to the target DB and, for bulk ingest, to source APIs (ALEdb, PMKbase, Pankb, BiGG).
- Input files staged:
  - Ingest JSON shaped like `scripts/examples/example_ingest.json`.
  - Cleanup JSON shaped like `scripts/examples/example_cleanup.json`.

## Initialize database schema
Use when starting from an empty database or after destructive test runs.
1) From `scripts/`, run:
   ```bash
   python interop_utils.py --init-db
   ```
2) This creates all required tables and seeds lookup values:
   - `entity`: `gene`, `strain`
   - `source_db`: `Bigg`, `ALEdb`, `PMKbase`, `Pankb`
3) The command is idempotent; running it multiple times is safe.

## Ingest from file
Use when ingesting payloads:
1) Validate input file:
   - Top-level key: `entities` (list).
   - Each entity requires `source_db` plus either:
     - `entity_type` of `gene` or `strain` with `local_id`, or
     - `gene_id` and `strain_id` for gene lookup (entity type is inferred as gene).
   - Optional `synonyms` as string or list; non-string values are stringified and trimmed.
2) Run from `scripts/`:
   ```bash
   python interop_utils.py --ingest examples/example_ingest.json
   ```
3) Success/failure is logged on the console. On JSON or DB errors, the process exits non-zero after rolling back the batch.
4) Post-check: spot-check new mappings in the DB or with `python interop_utils.py --list`

Notes:
- Unique IDs are generated per entity (`G-` or `S-` prefix, SHA256-derived suffix). Existing mappings are updated in place; registry rows are inserted if missing.
- When both `gene_id` and `strain_id` are provided, synonyms are fetched from NCBI (gene synonyms) and UniProt (protein IDs) if available.
- Batch size defaults to 5,000; adjust `BATCH_SIZE` in `scripts/utils/ingest.py` only after validating memory and DB load impact.
- Audit trail: new mappings create `audit_log` entries with `event_type` `Ingest` (`event_id`, `event_time`, `uid`, `event_type` columns).

## Bulk ingest from APIs
Use when syncing publicly exposed partner datasets.
1) Confirm outbound access to:
   - `https://aledb.org/interop-query/strains` and `/genes`
   - `https://www.pmkbase.com/interop-query/strains`
   - `https://pankb.org/interop-query/{strains|genes}`
   - `http://biggr-prod.northeurope.cloudapp.azure.com/interop-query/{strains|genes}`
2) Execute:
   ```bash
   python interop_utils.py --ingest-bulk
   ```
3) Monitor stdout for fetch errors and ingest counts.

Data hygiene applied automatically:
- Strain entities are ingested as-is.
- Gene local IDs are trimmed at whitespace, have non-word characters removed (`[^\w-]`), and are stripped.

## Targeted cleanup
Use to delete specific UIDs and the associated registry rows without touching other data.
1) Prepare a cleanup file (see `scripts/examples/example_cleanup.json`) with `uids: ["G-...", "S-..."]`.
2) Run:
   ```bash
   python interop_utils.py --cleanup examples/example_cleanup.json
   ```
3) Review per-UID status:
   - If a UID is missing in mappings, it is logged as not found and skipped.
   - Mapping is deleted first, then the matching registry row (if present).
   - Each successful deletion records an `audit_log` row with `event_type` `Removed` for that UID.
4) On errors, the current UID transaction is rolled back; processing continues with remaining UIDs. Final counts are printed.

## Full cleanup (destructive)
Use only for environment resets.
1) Run:
   ```bash
   python interop_utils.py --cleanup-all
   ```
2) Confirm with `y` when prompted. The script deletes all rows in `Synonym`, `Mapping`, and `Registry` and reports counts removed.
3) Abort if the prompt is not confirmed; no changes are applied.

## Post-run validation and logging
- Validation options:
  - Quick check: `python interop_utils.py --list` (suitable for small datasets).
  - Direct SQL queries against mapping/registry tables for row counts and spot checks.
- Logging:
  - Console messages capture batch progress and start/end timestamps.
  - DB transactions: commit per batch (ingest) or per UID (cleanup); any exception triggers rollback before exit.
- Audit records: `audit_log` accumulates `Ingest` and `Removed` events keyed by `uid`.

## UID merge and split procedures

Purpose
- Use synonyms to connect (merge) or disconnect (split) UIDs without rewriting mapping rows. UIDs remain deterministic per `(entity_type, local_id)`; synonyms define equivalence edges used by downstream consumers.

Merge UIDs (connect)
1) Identify UIDs to connect (e.g., `G-A...` and `G-B...`).
2) Choose a shared synonym strategy:
   - Add an existing synonym from UID B onto UID A, or
   - Add UID B’s string (e.g., `G-B...`) as a synonym of UID A, or
   - Add a brand-new common synonym to both A and B.
3) Prepare an ingest file that targets the UID you’re updating by providing the same `source_db`/`entity_type`/`local_id` that yields that UID, plus the synonym(s):
   ```json
   { "entities": [ { "source_db": "ALEdb", "entity_type": "gene", "local_id": "rpoB", "synonyms": ["G-BXXXXXX", "rpoB_alt"] } ] }
   ```
4) Run: `python interop_utils.py --ingest <file>.json`.
5) Post-check: query `synonyms` for both UIDs and confirm at least one identical string is present under each.

Split UIDs (disconnect)
1) Identify the shared synonym(s) creating the undesired connection.
2) Prepare a cleanup file using the `synonyms` key to remove only those pairs, not the entire UID:
   ```json
   { "synonyms": [ ["G-Axxxxxx", "shared_syn"], {"uid": "G-Bxxxxxx", "synonym": "shared_syn"} ] }
   ```
   Accepted shapes: list of pairs, list of objects with `uid`+`synonym`/`synonyms`, or a map `{ "UID": ["syn1", ...] }`.
3) Run: `python interop_utils.py --cleanup <file>.json`.
4) Post-check: ensure the removed synonyms no longer appear under the affected UIDs.

Auditing
- Merge: new synonym inserts log `Added synonym <value>` for the affected UID(s); if a synonym already exists, no duplicate is inserted or logged.
- Split: synonym-only deletions log `Removed synonym <value>` for each removed pair; full UID deletions log `Removed`.

## Operational guardrails
- Do not run ingest or cleanup without a filled `.env`; the connector will raise and exit.
- Avoid running bulk ingest against production without confirming source API stability; transient network failures will leave prior committed batches intact, so reruns are safe.
- For large ingest jobs, monitor DB load and consider reducing `BATCH_SIZE` if locks or timeouts occur.
