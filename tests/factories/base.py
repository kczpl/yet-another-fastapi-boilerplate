from typing import TYPE_CHECKING, Any, Generic, TypeVar

import factory
from factory.alchemy import SQLAlchemyModelFactory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class SQLAlchemyFactoryOptions(factory.base.FactoryOptions):
    sqlalchemy_session: AsyncSession | None


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    _meta: SQLAlchemyFactoryOptions

    def __call__(cls, *args: Any, **kwargs: Any) -> T:  # noqa: N805 — metaclass
        return super().__call__(*args, **kwargs)


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[reportIncompatibleVariableOverride]
        abstract = True
        sqlalchemy_session_persistence = None  # persistence handled manually below

    _meta: SQLAlchemyFactoryOptions

    @classmethod
    async def create(cls, **kwargs: Any) -> Any:
        session = cls._meta.sqlalchemy_session
        if session is None:
            raise RuntimeError(f"{cls.__name__}._meta.sqlalchemy_session is not set")

        instance = cls.build(**kwargs)
        session.add(instance)
        await session.flush()
        return instance
