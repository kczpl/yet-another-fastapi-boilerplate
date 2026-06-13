from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

import factory
from factory.alchemy import SQLAlchemyModelFactory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class SQLAlchemyFactoryOptions(factory.base.FactoryOptions):
    sqlalchemy_session: "AsyncSession | None"


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    _meta: SQLAlchemyFactoryOptions

    def __call__(cls, *args: Any, **kwargs: Any) -> T:
        return super().__call__(*args, **kwargs)


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:  # type: ignore[reportIncompatibleVariableOverride]
        abstract = True
        sqlalchemy_session_persistence = None  # persistence handled manually below

    _meta: SQLAlchemyFactoryOptions

    # Declarative FK derivation: {related_kwarg: {fk_field: attr_on_related}}.
    # When the related object is passed and the FK kwarg is absent, the FK is filled
    # from the related object. Example: {"item": {"item_id": "id"}}.
    _derive_fks: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    async def create(cls, **kwargs: Any) -> Any:
        session = cls._meta.sqlalchemy_session
        if session is None:
            raise RuntimeError(f"{cls.__name__}._meta.sqlalchemy_session is not set")

        for related_kwarg, fk_map in cls._derive_fks.items():
            related = kwargs.get(related_kwarg)
            if related is None:
                continue
            for fk_field, attr in fk_map.items():
                if fk_field not in kwargs:
                    kwargs[fk_field] = getattr(related, attr)

        instance = cls.build(**kwargs)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance
