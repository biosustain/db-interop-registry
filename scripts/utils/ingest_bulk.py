"""Ingest from internal databases."""
import sys
import os
import requests
    
from utils.models import Mapping
from utils.db_connector import get_session


def ingest_bulk_entities() -> None:
    """Ingest entities from internal databases."""
    session = get_session()
    
    # Make GET request to the API endpoint
    url = "https://aledb.org/interop-query/local-ids"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Print out the response
        print("Response from API:")
        print(data)
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}", file=sys.stderr)
    except ValueError as e:
        print(f"Error parsing JSON response: {e}", file=sys.stderr)