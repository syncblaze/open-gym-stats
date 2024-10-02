from fastapi import APIRouter

from .authentication import router as authentication_router
from .users import router as users_router

api_router = APIRouter()
api_router.include_router(authentication_router)
api_router.include_router(users_router)
