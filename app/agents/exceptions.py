from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class AgentNotFound(OrionError):
    code = "AGENT_NOT_FOUND"

    def __init__(self, detail: str = "Agent not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class AgentConflict(OrionError):
    code = "AGENT_CONFLICT"

    def __init__(self, detail: str = "Agent already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class AgentDisabled(OrionError):
    code = "AGENT_DISABLED"

    def __init__(self, detail: str = "Agent is disabled"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class AgentConfigInvalid(OrionError):
    code = "AGENT_CONFIG_INVALID"

    def __init__(self, detail: str = "Agent configuration invalid"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)



