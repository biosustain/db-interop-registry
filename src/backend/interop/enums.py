from enum import Enum

class ResourceType(str, Enum):
    """Available resource types."""
    gene = "gene"
    strain = "strain"