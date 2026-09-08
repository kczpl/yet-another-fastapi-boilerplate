from factory.declarations import Sequence

from app.repositories.items.models import Item
from tests.factories.base import BaseFactory, BaseMetaFactory


class ItemFactory(BaseFactory, metaclass=BaseMetaFactory[Item]):
    # Only fields without a model default; id / status / timestamps come from the
    # model and are loaded back by BaseFactory.create() after the flush.
    class Meta:  # type: ignore[reportIncompatibleVariableOverride]
        model = Item

    name = Sequence(lambda n: f"Item {n}")
    description = "An example item."
