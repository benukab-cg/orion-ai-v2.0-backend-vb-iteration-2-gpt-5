from __future__ import annotations

from fastapi import HTTPException, status


class OrionError(HTTPException):
    code: str = "ORION_ERROR"

    def __init__(self, status_code: int, detail: str, code: str | None = None):
        super().__init__(status_code=status_code, detail={"message": detail, "code": code or self.code})


class NotFoundError(OrionError):
    code = "NOT_FOUND"

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class ConflictError(OrionError):
    code = "CONFLICT"

    def __init__(self, detail: str = "Conflict"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class ValidationFailedError(OrionError):
    code = "VALIDATION_FAILED"

    def __init__(self, detail: str = "Validation failed"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class PermissionDeniedError(OrionError):
    code = "FORBIDDEN"

    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, self.code)


