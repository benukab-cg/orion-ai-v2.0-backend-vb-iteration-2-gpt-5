from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class AgentToolNotFound(OrionError):
    code = "AGENT_TOOL_NOT_FOUND"

    def __init__(self, detail: str = "Agent Tool not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class AgentToolConflict(OrionError):
    code = "AGENT_TOOL_CONFLICT"

    def __init__(self, detail: str = "Agent Tool already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class AgentToolDisabled(OrionError):
    code = "AGENT_TOOL_DISABLED"

    def __init__(self, detail: str = "Agent Tool is disabled"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class AgentToolConfigInvalid(OrionError):
    code = "AGENT_TOOL_VALIDATION_ERROR"

    def __init__(self, detail: str = "Agent Tool configuration invalid"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class AgentToolBindingInvalid(OrionError):
    code = "AGENT_TOOL_BINDING_INVALID"

    def __init__(self, detail: str = "Agent Tool bindings invalid"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)


class AgentToolAdapterNotFound(OrionError):
    code = "AGENT_TOOL_NOT_IMPLEMENTED"

    def __init__(self, detail: str = "Agent Tool kind/provider not supported"):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, detail, self.code)


class AgentToolInvokeNotImplemented(OrionError):
    code = "AGENT_TOOL_INVOKE_NOT_IMPLEMENTED"

    def __init__(self, detail: str = "Agent Tool invoke not implemented"):
        super().__init__(status.HTTP_501_NOT_IMPLEMENTED, detail, self.code)


