# interopdb-mcp
    
MCP server for the [Interop DB](https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io/), enabling LLMs like Claude Desktop to search and query genes, strains, and gene-strain pairs across multiple biological databases through natural language.
             
Interop DB is a federated registry that assigns unified identifiers to genes and strains across multiple biological databases. It integrates data from:    

- **[ALEdb](https://aledb.org)** -- Adaptive Laboratory Evolution Database
- **[BiGGr](https://biggr.org)** -- Knowledgebase of genome-scale metabolic network reconstructions
- **[PanKB](https://pankb.org)** -- Pangenome Knowledge Base
- **[PMkbase](https://www.pmkbase.com)** -- Phenotype MicroArray Knowledge Base

Interop DB also has a [Python client and CLI](https://pypi.org/project/interopdb/) for programmatic use. This MCP package wraps the client using FastMCP. For developers who prefer coding directly, install the `interopdb` package instead.
     
## Installation

```bash
pip install interopdb-mcp
```

## Usage with Claude Desktop

interopdb-mcp runs as a local MCP server over stdio hosted by Claude Desktop. First, find the absolute path to the installed package:   

```bash
which interopdb-mcp
```     
Copy and add the path to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "interopdb-mcp": {
      "command": "/full/path/to/interopdb-mcp"
    }
  }
}
```

Then restart Claude Desktop. You can now ask Claude questions like:

- "Find data for gene rpoB"
- "Look up strain 511145 across all databases"
- "What data is available for gene thrL in strain 511145?"
- "Search for dnaA in the registry"
- "What gene-strain relationships exist for GCF_031662355.1 in the registry?"

## Available Tools

| Tool | Description |
|---|---|
| `get_gene` | Query a gene by local ID or UID |
| `get_strain` | Query a strain by local ID or UID |
| `get_pair` | Query a gene-strain pair by local ID |
| `search_entities` | Search entities by local ID, UID, or synonym |
| `search_relationships` | Search gene-strain relationships by a gene or strain local ID |
