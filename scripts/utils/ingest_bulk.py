"""Ingest from internal databases."""

import sys
import time
import requests
import re
from typing import List, Dict

from utils.ingest import start_ingest
from utils.db_connector import get_session

def get_entities(baseURL: str, sourceDB: str, genes: bool = True) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch strains and genes from API endpoints and format them as entities.
    
    Args:
        baseURL: Base URL for the API endpoints
        sourceDB: Source database name (e.g., "ALEdb", "PMKbase", "Pankb")
    
    Returns:
        Dictionary containing a list of entity objects with source_db, entity_type, and local_id
    """
    entities = []
    
    # Fetch strains
    try:
        strains_response = requests.get(f"{baseURL}/interop-query/strains")
        strains_response.raise_for_status()
        strains_data = strains_response.json()
        
        # Handle both formats: {"strains": [...]} and [...]
        if isinstance(strains_data, dict):
            strains_list = strains_data.get("strains", [])
        else:
            strains_list = strains_data
        
        # Add strain entities
        for strain in strains_list:
            entities.append({
                "source_db": sourceDB,
                "entity_type": "strain",
                "local_id": strain
            })
    except requests.RequestException as e:
        print(f"Error fetching strains: {e}")
    
    if not genes:
        return {"entities": entities}
    
    # Fetch genes
    try:
        genes_response = requests.get(f"{baseURL}/interop-query/genes")
        genes_response.raise_for_status()
        genes_data = genes_response.json()
        
        # Handle both formats: {"genes": [...]} and [...]
        if isinstance(genes_data, dict):
            genes_list = genes_data.get("genes", [])
        else:
            genes_list = genes_data
        
        # Add gene entities
        for gene in genes_list:
            entities.append({
                "source_db": sourceDB,
                "entity_type": "gene",
                "local_id": gene
            })
    except requests.RequestException as e:
        print(f"Error fetching genes: {e}")
    
    return {"entities": entities}


def ingest_bulk_entities() -> Dict[str, List[Dict[str, str]]]:
    """Ingest entities from internal databases."""

    print("Ingesting entities from internal databases...")
    print("Fetching entities from ALEdb...")
    aleDBEntities = get_entities("https://aledb.org", "ALEdb")

    print("Fetching entities from PMKbase...")
    pmkBaseEntities = get_entities("https://www.pmkbase.com", "PMKbase", genes=False)

    print("Fetching entities from Pankb...")
    pankbEntities = get_entities("http://pankb-preprod.northeurope.cloudapp.azure.com/", "Pankb")

    print("Fetching entities from BiGG...")
    biggEntities = get_entities("http://biggr-prod.northeurope.cloudapp.azure.com/", "Bigg")
    
    # Combine all entities into one object
    combined_entities = {
        "entities": (
            aleDBEntities.get("entities", []) +
            pmkBaseEntities.get("entities", []) + 
            pankbEntities.get("entities", []) +
            biggEntities.get("entities", [])
        )
    }

    for entity in combined_entities["entities"]:
        # if entity type is strain, skip cleanup
        if entity["entity_type"] == "strain":
            continue

        local_id = entity["local_id"]

        if " " in local_id:
            local_id = local_id.split(" ")[0]
        
        # Remove special characters like "[", "]", "?", etc.
        local_id = re.sub(r'[^\w\-]', '', local_id)
        
        local_id = local_id.strip()
        entity["local_id"] = local_id

    entities = combined_entities["entities"]
    if not isinstance(entities, list):
        print("Error: 'entities' must be a list")
        sys.exit(1)

    session = get_session()

    print(f"Starting ingestion of {len(entities)} entities...")

    start_time = time.time()
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    start_ingest(session, entities)
    end_time = time.time()
    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print(f"Ingestion completed in {end_time - start_time:.2f} seconds.")
    