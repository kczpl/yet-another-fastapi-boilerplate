from typing import TYPE_CHECKING, Any

import factory
from factory.alchemy import SQLAlchemyModelFactory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyFactoryOptions(factory.base.FactoryOptions):
    sqlalchemy_session: AsyncSession | None


class BaseFactory[T](SQLAlchemyModelFactory):
    class Meta:  # type: ignore[reportIncompatibleVariableOverride]
        abstract = True
        sqlalchemy_session_persistence = None  # persistence handled manually below

    _meta: SQLAlchemyFactoryOptions

    @classmethod
    async def create(cls, **kwargs: Any) -> T:
        session = cls._meta.sqlalchemy_session
        if session is None:
            raise RuntimeError(f"{cls.__name__}._meta.sqlalchemy_session is not set")

        instance = cls.build(**kwargs)
        session.add(instance)
        await session.flush()
        return instance
