# interopdb

Python client and CLI for the [Interop DB Registry](https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io/) API.

Interop DB is a federated registry that assigns unified identifiers to genes and strains across multiple biological databases, enabling cross-database queries with a single search. It integrates data from:

- **ALEdb** -- Adaptive Laboratory Evolution Database 
- **BiGGr** -- Knowledgebase of genome-scale metabolic network reconstructions
- **PanKB** -- Pangenome Knowledge Base (genes, strains, pangenomics)
- **PMkbase** -- Phenotype MicroArray Knowledge Base (strains, phenotypes)

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

# Save to file
interopdb gene rpoB -o result.json
```
