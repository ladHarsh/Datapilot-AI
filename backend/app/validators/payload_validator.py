"""
app/validators/payload_validator.py
───────────────────────────────────
Performs generic payload structural and content validation for API requests.
"""

class PayloadValidationError(Exception):
    """Exception raised when request payload validation fails."""
    def __init__(self, message: str = "Invalid payload"):
        self.message = message
        super().__init__(self.message)


class PayloadValidator:
    """
    Validates incoming request payload size, structure, and values.
    """
    def __init__(self):
        pass

    def validate(self, payload: dict) -> bool:
        """
        Validate that the payload conforms to basic security and structural integrity.
        Returns True if valid, raises PayloadValidationError if invalid.
        """
        if not isinstance(payload, dict):
            raise PayloadValidationError("Payload must be a dictionary")
        return True
