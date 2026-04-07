from fastapi import APIRouter

from .categories import router as categories_router
from .categories_query import router as categories_query_router
from .documents_core import router as documents_core_router
from .documents_ops import router as documents_ops_router
from .latest import router as latest_router
from .migrate import router as migrate_router
from .tags import router as tags_router

router = APIRouter()
router.include_router(categories_router)
router.include_router(categories_query_router)

# static routes first
router.include_router(latest_router)
router.include_router(tags_router)
router.include_router(documents_ops_router)  # includes /v1/plan/documents/merge

# dynamic routes after static routes
router.include_router(documents_core_router)

router.include_router(migrate_router)