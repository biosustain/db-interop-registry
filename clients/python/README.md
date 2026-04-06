# interopdb

Python client and CLI for the [Interop DB](https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io/) API.

Interop DB is a federated registry that assigns unified identifiers to genes and strains across multiple biological databases, enabling cross-database queries with a single search. It integrates data from:

- **[ALEdb](https://aledb.org)** -- Adaptive Laboratory Evolution Database
- **[BiGGr](https://biggr.org)** -- Knowledgebase of genome-scale metabolic network reconstructions
- **[PanKB](https://pankb.org)** -- Pangenome Knowledge Base
- **[PMkbase](https://www.pmkbase.com)** -- Phenotype MicroArray Knowledge Base

## Installation

```bash
pip install interopdb
```

## Python API

```python
from interopdb import InteropClient

client = InteropClient()

# Query a gene
result = client.get_gene("rpoB")
print(result["uid"], result["attributes"])

# Query a strain
result = client.get_strain("511145")

# Query a gene-strain pair
result = client.get_pair("rpoB", "511145")
for source in result["sources"]:
    print(source["source"], source["data"])

# Search entities by local ID, UID, or synonym
result = client.search_entities("dnaA")
for entity in result["entities"]:
    print(entity["local_id"], entity["source_db_name"])

# Search gene-strain relationships by a gene or strain
result = client.search_relationships("rpoB")
for rel in result["relationships"]:
    print(rel["gene_local_id"], rel["strain_local_id"])

# Save result to JSON
client.save_json(result, "output.json")
```

## CLI

```bash
# Query entities
interopdb gene rpoB
interopdb strain 511145

# Query a gene-strain pair
interopdb pair rpoB 511145

# Search entities
interopdb search-entities dnaA

# Search relationships
interopdb search-relationships GCF_031662355.1

# Save to file
interopdb gene rpoB -o result.json
```

## Changelog

### 0.2.0
- Add `search_entities()` and `search_relationships()` to Python API
- Add `search-entities` and `search-relationships` CLI commands

### 0.1.0
- Initial release with `get_gene`, `get_strain`, `get_pair` Python API and CLI
