from fastapi import APIRouter, HTTPException, Body, Path, Query
from pydantic import BaseModel
from typing import Optional
from conversation_manager import conversation_manager
router = APIRouter()
# ========== 请求模型 ==========
class ConversationCreateRequest(BaseModel):
    system_prompt: Optional[str] = None
    project_id: int = 0
    name: Optional[str] = None
    model: Optional[str] = None
    assistance_role: Optional[str] = None
    status: Optional[int] = 0  # 新增：会话状态（0: 正常，1: 存档等）
class UpdateConversationRequest(BaseModel):
    project_id: Optional[int] = None
    name: Optional[str] = None
    model: Optional[str] = None
    assistance_role: Optional[str] = None
    status: Optional[int] = None  # 新增：会话状态
# ========== 接口实现 ==========
@router.post("/v1/chat/conversations")
async def create_conversation_api(request: ConversationCreateRequest = Body(...)):
    conversation_id = conversation_manager.create_conversation(
        system_prompt=request.system_prompt,
        project_id=request.project_id,
        name=request.name,
        model=request.model,
        assistance_role=request.assistance_role,
        status=request.status or 0
    )
    # 为向前兼容保留旧返回结构，只返回 conversation_id
    return {"conversation_id": conversation_id}
@router.get("/v1/chat/conversations/grouped")
async def get_grouped_conversations():
    grouped = conversation_manager.get_all_conversations_grouped_by_project()
    return grouped
@router.get("/v1/chat/conversations")
async def list_conversations(
    project_id: Optional[int] = Query(None, description="按项目ID筛选"),
    status: Optional[int] = Query(None, description="按会话状态筛选（0/1）")
):
    """
    新增：获取会话列表，支持 project_id 与 status 条件筛选。
    返回包含 status / updated_at 等字段，向前兼容不影响旧接口。
    """
    return conversation_manager.get_conversations(project_id=project_id, status=status)
@router.get("/v1/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str = Path(...)):
    """
    新增：根据会话ID获取单条会话详情。
    """
    try:
        convo = conversation_manager.get_conversation_by_id(conversation_id)
        return convo
    except KeyError:
        raise HTTPException(status_code=404, detail="Conversation not found")
@router.put("/v1/chat/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str = Path(...),
    request: UpdateConversationRequest = Body(...)
):
    success = conversation_manager.update_conversation(
        conversation_id,
        project_id=request.project_id,
        name=request.name,
        model=request.model,
        assistance_role=request.assistance_role,
        status=request.status
    )
    if success:
        return {"message": "Conversation updated"}
    else:
        raise HTTPException(status_code=404, detail="Conversation not found")
@router.delete("/v1/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str = Path(...)):
    success = conversation_manager.delete_conversation(conversation_id)
    if success:
        return {"message": "Conversation deleted"}
    else:
        raise HTTPException(status_code=404, detail="Conversation not found")