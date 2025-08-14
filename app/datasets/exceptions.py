from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class DatasetNotFound(OrionError):
    code = "DATASET_NOT_FOUND"

    def __init__(self, detail: str = "Dataset not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class DatasetConflict(OrionError):
    code = "DATASET_CONFLICT"

    def __init__(self, detail: str = "Dataset already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class DatasetValidationError(OrionError):
    code = "DATASET_VALIDATION_ERROR"

    def __init__(self, detail: str = "Dataset validation failed"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class DatasetUnknownType(OrionError):
    code = "DATASET_UNKNOWN_TYPE"

    def __init__(self, detail: str = "Unknown dataset type"):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail, self.code)


class DatasetNotImplemented(OrionError):
    code = "DATASET_NOT_IMPLEMENTED"

    def __init__(self, detail: str = "Dataset operation not implemented"):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, detail, self.code)


class DatasetDisabled(OrionError):
    code = "DATASET_DISABLED"

    def __init__(self, detail: str = "Dataset or Datasource is disabled"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class DatasetAccessDenied(OrionError):
    code = "DATASET_ACCESS_DENIED"

    def __init__(self, detail: str = "Access denied"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, self.code)


class DatasetRLSDenied(OrionError):
    code = "DATASET_RLS_DENIED"

    def __init__(self, detail: str = "Row-level security denied the request"):
        super().__init__(status.HTTP_403_FORBIDDEN, detail, self.code)


