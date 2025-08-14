from __future__ import annotations

from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import Principal, get_current_principal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_principal(principal: Principal = Depends(get_current_principal)) -> Principal:
    return principal


