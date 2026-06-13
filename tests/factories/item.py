from factory.declarations import LazyFunction, Sequence

from app.repositories.items.models import Item
from app.utils.time import utc_now
from app.utils.uuid import uuid7
from tests.factories.base import BaseFactory, BaseMetaFactory


class ItemFactory(BaseFactory, metaclass=BaseMetaFactory[Item]):
    class Meta:  # type: ignore[reportIncompatibleVariableOverride]
        model = Item

    id = LazyFunction(uuid7)
    name = Sequence(lambda n: f"Item {n}")
    description = "An example item."
    status = "active"
    created_at = LazyFunction(utc_now)
    updated_at = LazyFunction(utc_now)
