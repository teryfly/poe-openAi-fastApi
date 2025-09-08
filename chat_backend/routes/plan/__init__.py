from fastapi import APIRouter
from .categories import router as categories_router
from .documents import router as documents_router

router = APIRouter()
router.include_router(categories_router)
router.include_router(documents_router)