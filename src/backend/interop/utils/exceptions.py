class ResourceNotFoundError(Exception):
    """Exception raised when a resource is not found."""
    def __init__(self, detail: str):
        self.detail = detail
        self.status_code = 404
        super().__init__(self.detail)

class InvalidResourceTypeError(Exception):
    """Exception raised for invalid resource types."""
    def __init__(self, detail: str):
        self.detail = detail
        self.status_code = 400
        super().__init__(self.detail)

class DatabaseInconsistencyError(Exception):
    """Exception raised for database inconsistencies."""
    def __init__(self, detail: str):
        self.detail = detail
        self.status_code = 500
        super().__init__(self.detail)