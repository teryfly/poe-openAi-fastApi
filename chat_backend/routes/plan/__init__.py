from fastapi import APIRouter
from .categories import router as categories_router
from .latest import router as latest_router
from .tags import router as tags_router
from .documents import router as documents_router
from .migrate import router as migrate_router

router = APIRouter()
router.include_router(categories_router)

# Register static document routes first
router.include_router(latest_router)
router.include_router(tags_router)

# Register dynamic document_id routes after static ones
router.include_router(documents_router)
router.include_router(migrate_router)