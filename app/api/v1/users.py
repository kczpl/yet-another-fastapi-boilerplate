from fastapi import APIRouter, Depends, status
from app.models.user.schemas import CurrentUser
from app.models.user.dependencies import auth_user
from app.models.user.models import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=CurrentUser,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Returns the authenticated user's profile information",
)
async def me(current_user: User = Depends(auth_user)):
    return current_user
