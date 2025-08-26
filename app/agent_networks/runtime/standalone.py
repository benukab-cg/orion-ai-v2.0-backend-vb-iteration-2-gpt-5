from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.security import Principal
from app.agent_networks.schemas import AgentNetworkSpec
from app.agent_networks.exceptions import AgentNetworkInvalid
from app.agents.models import Agent
from app.agents.services import AgentService


def invoke_standalone(db: Session, principal: Principal, spec: AgentNetworkSpec, payload: dict) -> dict:
    if len(spec.nodes) != 1:
        raise AgentNetworkInvalid("Standalone network must have a single node")
    node = spec.nodes[0]
    if not node.agent_id:
        raise AgentNetworkInvalid("Standalone network must reference an agent node")
    service = AgentService(db, principal)
    return service.invoke(str(node.agent_id), {
        "input": payload.get("input"),
        "variables": payload.get("variables") or {},
        "tool_overrides": (payload.get("runtime_overrides") or {}).get("tool_overrides") or {},
        "llm_overrides": (payload.get("runtime_overrides") or {}).get("llm_overrides") or {},
    })


