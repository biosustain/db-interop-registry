# Database Endpoints (APIs used by Interop)

Endpoints exposed by the databases that this Interop service consumes. These calls pull lists of local IDs for seeding the registry, fetch attributes for individual entities, and fetch attributes for specific gene+strain pairs. All calls are unauthenticated.

## Operation types

- List endpoints (GET): `.../interop-query/strains` and `.../interop-query/genes` return the full set of local IDs each database publishes. Interop uses them for ingest. PMKbase exposes only the strains list.

- Entity lookup (single or batch, POST): `.../interop-query/query-by-gene` or `.../interop-query/query-by-strain` with `{"ids": ["<id1>", ...]}` to fetch attributes for one or many IDs. PMKbase supports only the strain endpoint; others support both.

- Pair lookup (POST): `.../interop-query/query-by-pair` with `{"pairs": [{"gene": "<gene>", "strain": "<strain>"}]}` to fetch attributes for specific gene+strain combinations. Supported by ALEdb, BiGG, PanKB.

## Request/response shapes
- List responses may be wrapped (`{"strains": [...]}`, `{"genes": [...]}`) or bare arrays (`["..."]`).
- Lookup bodies must be JSON arrays of IDs (or pairs for pair queries). Responses are database-specific JSON structures.
- `scripts/utils/ingest_bulk.py` sanitizes gene IDs (trim spaces, drop special chars except hyphen/word chars); strains are taken as-is.

## Capabilities by database
- **ALEdb** (`https://aledb.org`)
  - Bulk: `GET /interop-query/strains`, `GET /interop-query/genes`
  - Lookup: `POST /interop-query/query-by-gene`, `POST /interop-query/query-by-strain`
  - Pair: `POST /interop-query/query-by-pair`
- **BiGG** (`https://biggr.org/`)
  - Bulk: `GET /interop-query/strains`, `GET /interop-query/genes`
  - Lookup: `POST /interop-query/query-by-gene`, `POST /interop-query/query-by-strain`
  - Pair: `POST /interop-query/query-by-pair`
- **PanKB** (`https://pankb.org/`)
  - Bulk: `GET /interop-query/strains`, `GET /interop-query/genes`
  - Lookup: `POST /interop-query/query-by-gene`, `POST /interop-query/query-by-strain`
  - Pair: `POST /interop-query/query-by-pair`
- **PMKbase** (`https://pmkbase.com` for lookups, `https://www.pmkbase.com` for bulk)
  - Bulk: `GET /interop-query/strains` (genes are intentionally skipped during bulk ingest)
  - Lookup: `POST /interop-query/query-by-strain`
  - Lookup gene: not supported
  - Pair: not supported

## Minimal curl examples
```bash
# Bulk strains (ALEdb)
curl -s https://aledb.org/interop-query/strains

# Single gene lookup (ALEdb)
curl -s -X POST https://aledb.org/interop-query/query-by-gene \
  -H "Content-Type: application/json" \
  -d '{"ids": ["rpoB"]}'

# Single strain lookup (PMKbase)
curl -s -X POST https://pmkbase.com/interop-query/query-by-strain \
  -H "Content-Type: application/json" \
  -d '{"ids": ["strain-id"]}'

# Gene+strain pair lookup (BiGG)
curl -s -X POST https://biggr.org/interop-query/query-by-pair \
  -H "Content-Type: application/json" \
  -d '{"pairs": [{"gene": "gene-id", "strain": "strain-id"}]}'
```
