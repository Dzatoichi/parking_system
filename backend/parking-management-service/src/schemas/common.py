from typing import TypeVar, Generic, Optional, Any
from pydantic import Field, ConfigDict
from pydantic.generics import GenericModel

from .base_schema import BaseSchema

T = TypeVar("T")


class PaginatedResponse(GenericModel, Generic[T]):
    """
    Универсальная обёртка для списков с пагинацией.

    Использование в роутере:
        @router.get("/spots/{parking_id}", response_model=PaginatedResponse[SpotReadShort])
        async def get_spots(parking_id: int, page: int = 1, size: int = 50):
            ...
            return PaginatedResponse(items=spots, total=total, page=page, size=size)
    """
    items: list[T]
    total: int = Field(description="Общее количество записей в БД")
    page: int = Field(ge=1, default=1)
    size: int = Field(ge=1, le=200, default=50)
    pages: int = Field(description="Общее количество страниц")

    @classmethod
    def create(cls, items: list, total: int, page: int, size: int) -> "PaginatedResponse":
        pages = (total + size - 1) // size if size > 0 else 1
        return cls(items=items, total=total, page=page, size=size, pages=pages)

    model_config = ConfigDict(from_attributes=True)

class ErrorResponse(BaseSchema):
    """
    Стандартный формат ошибки.

    Используй так в роутере:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(code="SPOT_NOT_FOUND", message="Место не найдено").model_dump()
        )
    """
    code: str = Field(description="Машиночитаемый код ошибки", examples=["SPOT_NOT_FOUND"])
    message: str = Field(description="Человекочитаемое сообщение")
    details: Optional[dict] = Field(default=None, description="Доп. информация (валидационные ошибки и т.п.)")


class SuccessResponse(BaseSchema):
    """
    Простое подтверждение успешной операции (когда отдавать объект нет смысла).

    Пример: подтверждение принятия задания трекинга.
    """
    ok: bool = True
    message: str = "Операция выполнена успешно"