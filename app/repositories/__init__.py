from app.repositories.items.models import Item

# Every model must be imported here so Base.metadata is fully populated (Alembic
# autogenerate and the test schema builder both rely on it). Add new models below.
__all__ = ["Item"]
