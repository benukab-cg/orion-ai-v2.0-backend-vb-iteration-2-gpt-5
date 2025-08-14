from fastapi import FastAPI

from app.datasources.controllers import router as datasources_router
from app.datasets.controllers import router as datasets_router


app = FastAPI(
	title="Orion AI Platform Backend",
	version="0.1.0",
)


app.include_router(datasources_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")

