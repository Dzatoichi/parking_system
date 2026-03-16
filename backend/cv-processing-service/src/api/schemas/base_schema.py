"""
Базовая схема для DTO слоя API.
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Общий конфиг pydantic-схем."""

    model_config = ConfigDict(from_attributes=True)
