from fastapi import APIRouter, Depends
from app.models.user.schemas import CurrentUser
from app.models.user.dependencies import auth_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(current_user: CurrentUser = Depends(auth_user)):
    return current_user
