from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class AgentNetworkNotFound(OrionError):
    code = "AGENT_NETWORK_NOT_FOUND"

    def __init__(self, detail: str = "Agent network not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class AgentNetworkConflict(OrionError):
    code = "AGENT_NETWORK_CONFLICT"

    def __init__(self, detail: str = "Agent network already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class AgentNetworkInvalid(OrionError):
    code = "AGENT_NETWORK_INVALID"

    def __init__(self, detail: str = "Agent network specification invalid"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)



