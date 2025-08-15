from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class AIModelNotFound(OrionError):
    code = "AIMODEL_NOT_FOUND"

    def __init__(self, detail: str = "AI Model not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class AIModelConflict(OrionError):
    code = "AIMODEL_CONFLICT"

    def __init__(self, detail: str = "AI Model already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class AIModelValidationError(OrionError):
    code = "AIMODEL_VALIDATION_ERROR"

    def __init__(self, detail: str = "AI Model validation failed"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class AIModelUnknownType(OrionError):
    code = "AIMODEL_UNKNOWN_TYPE"

    def __init__(self, detail: str = "Unknown AI Model type"):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, self.code)


class AIModelNotImplemented(OrionError):
    code = "AIMODEL_NOT_IMPLEMENTED"

    def __init__(self, detail: str = "AI Model operation not implemented"):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, detail, self.code)



