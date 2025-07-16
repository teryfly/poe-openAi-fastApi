from fastapi import APIRouter, HTTPException, Body, Path
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


class UpdateConversationRequest(BaseModel):
    project_id: Optional[int] = None
    name: Optional[str] = None
    model: Optional[str] = None


# ========== 接口实现 ==========

@router.post("/v1/chat/conversations")
async def create_conversation_api(request: ConversationCreateRequest = Body(...)):
    conversation_id = conversation_manager.create_conversation(
        system_prompt=request.system_prompt,
        project_id=request.project_id,
        name=request.name,
        model=request.model
    )
    return {"conversation_id": conversation_id}


@router.get("/v1/chat/conversations/grouped")
async def get_grouped_conversations():
    grouped = conversation_manager.get_all_conversations_grouped_by_project()
    return grouped


@router.put("/v1/chat/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str = Path(...),
    request: UpdateConversationRequest = Body(...)
):
    success = conversation_manager.update_conversation(
        conversation_id,
        project_id=request.project_id,
        name=request.name,
        model=request.model
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
