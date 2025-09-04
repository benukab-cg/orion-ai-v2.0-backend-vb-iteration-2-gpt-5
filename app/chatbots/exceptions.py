from __future__ import annotations

from fastapi import status

from app.core.exceptions import OrionError


class ChatbotNotFound(OrionError):
    code = "CHATBOT_NOT_FOUND"

    def __init__(self, detail: str = "Chatbot not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail, self.code)


class ChatbotConflict(OrionError):
    code = "CHATBOT_CONFLICT"

    def __init__(self, detail: str = "Chatbot already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail, self.code)


class ChatbotInvalid(OrionError):
    code = "CHATBOT_INVALID"

    def __init__(self, detail: str = "Chatbot request invalid"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, self.code)



