from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """
    Базовая схема для всех остальных схем.

    from_attributes=True позволяет создавать схемы из ORM-объектов:
        spot = await dao.get_by_id(1)  # SQLAlchemy объект
        SpotRead.model_validate(spot)  # работает благодаря from_attributes
    """
    model_config = ConfigDict(from_attributes=True)