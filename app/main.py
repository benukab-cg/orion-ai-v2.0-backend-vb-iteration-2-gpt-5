from fastapi import FastAPI

from app.datasources.controllers import router as datasources_router
from app.datasets.controllers import router as datasets_router
from app.ai_models.controllers import router as ai_models_router
from app.agent_tools.controllers import router as agent_tools_router
from app.agent_networks.controllers import router as agent_networks_router
from app.agents.controllers import router as agents_router


app = FastAPI(
	title="Orion AI Platform Backend",
	version="0.1.0",
)


app.include_router(datasources_router, prefix="/api/v1")
app.include_router(datasets_router, prefix="/api/v1")
app.include_router(ai_models_router, prefix="/api/v1")
app.include_router(agent_tools_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(agent_networks_router, prefix="/api/v1")

