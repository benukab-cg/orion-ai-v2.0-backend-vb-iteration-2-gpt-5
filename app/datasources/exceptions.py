from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class DataSourceNotFound(OrionError):
    code = "DS_NOT_FOUND"

    def __init__(self, detail: str = "Datasource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class DataSourceConflict(OrionError):
    code = "DS_CONFLICT"

    def __init__(self, detail: str = "Datasource already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class DataSourceValidationError(OrionError):
    code = "DS_VALIDATION_ERROR"

    def __init__(self, detail: str = "Datasource validation failed"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class DataSourceUnknownType(OrionError):
    code = "DS_UNKNOWN_TYPE"

    def __init__(self, detail: str = "Unknown datasource type"):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, self.code)


class DataSourceNotImplemented(OrionError):
    code = "DS_NOT_IMPLEMENTED"

    def __init__(self, detail: str = "Datasource operation not implemented"):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, detail, self.code)


