from app.models.base.schemas import Base
from app.models.user.models import UserRole
from datetime import datetime


class CurrentUser(Base):
    id: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
