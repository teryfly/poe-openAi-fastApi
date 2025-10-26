from pydantic import BaseModel
from typing import Optional, List, Literal

# -------- Category Models --------
class PlanCategoryModel(BaseModel):
    id: int
    name: str
    prompt_template: str
    message_method: str
    auto_save_category_id: Optional[int] = None
    is_builtin: bool
    summary_model: Optional[str] = "GPT-4.1"
    created_time: Optional[str] = None

class PlanCategoryCreateRequest(BaseModel):
    name: str
    prompt_template: str
    message_method: str
    auto_save_category_id: Optional[int] = None
    is_builtin: Optional[bool] = False
    summary_model: Optional[str] = "GPT-4.1"

class PlanCategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    prompt_template: Optional[str] = None
    message_method: Optional[str] = None
    auto_save_category_id: Optional[int] = None
    is_builtin: Optional[bool] = None
    summary_model: Optional[str] = None

# -------- Document Models (moved from routes_plan.py unchanged) --------
class PlanDocumentCreateRequest(BaseModel):
    project_id: int
    category_id: int
    filename: str
    content: str
    version: Optional[int] = 1
    source: Optional[Literal['user', 'server', 'chat']] = 'user'
    related_log_id: Optional[int] = None

class PlanDocumentUpdateRequest(BaseModel):
    filename: Optional[str] = None
    content: Optional[str] = None
    source: Optional[Literal['user', 'server', 'chat']] = None

class PlanDocumentResponse(BaseModel):
    id: int
    project_id: int
    category_id: int
    filename: str
    content: str
    version: int
    source: str
    related_log_id: Optional[int]
    created_time: Optional[str] = None

# -------- Merge API Models --------
class MergeDocumentsRequest(BaseModel):
    document_ids: List[int]

class MergeDocumentsResponse(BaseModel):
    count: int
    merged: str