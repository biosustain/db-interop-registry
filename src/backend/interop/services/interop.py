from typing import Dict, Any
import httpx

class InteropService:
    """Service for handling interoperability API calls."""
    
    @staticmethod
    def fetch_attributes(
        source_db_id: int, 
        entity_type_id: int, 
        local_id: str
    ) -> Dict[str, Any]:
        """
        Fetch interop attributes from external sources.
        
        Args:
            source_db_id: Source database identifier
            entity_type_id: Entity type identifier (1=gene, 2=strain)
            local_id: Local identifier
            
        Returns:
            Dictionary containing attributes or error information
        """
        try:
            if source_db_id == 1:
                return InteropService._fetch_from_biggr(entity_type_id, local_id)
       
            elif source_db_id == 2:
                return InteropService._fetch_from_aledb(entity_type_id, local_id)    
             
            elif source_db_id == 3:
                return InteropService._fetch_from_pmkbase(entity_type_id, local_id)
            
            elif source_db_id == 4:
                return InteropService._fetch_from_pankb(entity_type_id, local_id)
            else:
                return {}
                
        except httpx.HTTPError as e:
            return {"error": f"interop request failed: {str(e)}"}
    
    @staticmethod
    def _fetch_from_aledb(entity_type_id: int, local_id: str) -> Dict[str, Any]:
        """Fetch from AleDB."""
        if entity_type_id == 1:
            endpoint = "gene"
        elif entity_type_id == 2:
            endpoint = "strain"
        else:
            return {}
        
        url = f"https://aledb.org/interop-query/{endpoint}"
        return InteropService._make_request(url, local_id)
    
    @staticmethod
    def _fetch_from_biggr(entity_type_id: int, local_id: str) -> Dict[str, Any]:
        """Fetch from BiggR."""
        if entity_type_id == 1:
            endpoint = "gene"
        elif entity_type_id == 2:
            endpoint = "strain"
        else:
            return {}
        
        url = f"http://biggr-prod.northeurope.cloudapp.azure.com/interop-query/query-by-{endpoint}"
        return InteropService._make_request(url, local_id)
    
    @staticmethod
    def _fetch_from_pmkbase(entity_type_id: int, local_id: str) -> Dict[str, Any]:
        """Fetch from PMKBase."""
        if entity_type_id == 1:
            endpoint = "gene"
        elif entity_type_id == 2:
            endpoint = "strain"
        else:
            return {}
        
        url = f"https://pmkbase.com/interop-query/query-by-{endpoint}"
        return InteropService._make_request(url, local_id)

    @staticmethod
    def _fetch_from_pankb(entity_type_id: int, local_id: str) -> Dict[str, Any]:
        """Fetch from PanKB."""
        if entity_type_id == 1:
            endpoint = "gene"
        elif entity_type_id == 2:
            endpoint = "strain"
        else:
            return {}

        url = f"http://pankb-preprod.northeurope.cloudapp.azure.com/interop-query/query-by-{endpoint}"
        return InteropService._make_request(url, local_id)

    @staticmethod
    def _make_request(url: str, local_id: str) -> Dict[str, Any]:
        """Make HTTP request to external API."""
        payload = {"ids": [local_id]}
        with httpx.Client(timeout=120) as client:
            response = client.post(
                url, 
                json=payload, 
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()