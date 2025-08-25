from fastapi import APIRouter, HTTPException, Body, Path
from pydantic import BaseModel
from typing import List, Dict, Any
from db import get_conn

router = APIRouter()

# ========== 数据模型 ==========

class ProjectDocumentReferencesRequest(BaseModel):
    document_ids: List[int]

class ConversationDocumentReferencesRequest(BaseModel):
    document_ids: List[int]

class DocumentReferenceOperationResponse(BaseModel):
    message: str
    added_count: int
    removed_count: int
    current_references: List[int]

# ========== 工具函数 ==========

def _validate_project_exists(project_id: int):
    """验证项目是否存在"""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM projects WHERE id=%s", (project_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Project not found")

def _validate_conversation_exists(conversation_id: str):
    """验证会话是否存在并返回项目ID"""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT project_id FROM conversations WHERE id=%s", (conversation_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return row[0]

def _validate_documents_exist_in_project(document_ids: List[int], project_id: int):
    """验证文档是否存在于指定项目中"""
    if not document_ids:
        return
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(document_ids))
            cursor.execute(
                f"SELECT id FROM plan_documents WHERE id IN ({placeholders}) AND project_id = %s",
                tuple(document_ids + [project_id])
            )
            found_ids = [row[0] for row in cursor.fetchall()]
            missing_ids = set(document_ids) - set(found_ids)
            if missing_ids:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Documents not found in project: {sorted(missing_ids)}"
                )

def _get_current_project_references(project_id: int) -> List[int]:
    """获取项目当前的引用文档ID列表"""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT document_id FROM document_references WHERE project_id=%s AND reference_type='project'",
                (project_id,)
            )
            return [row[0] for row in cursor.fetchall()]

def _get_current_conversation_references(conversation_id: str) -> List[int]:
    """获取会话当前的引用文档ID列表"""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT document_id FROM document_references WHERE conversation_id=%s AND reference_type='conversation'",
                (conversation_id,)
            )
            return [row[0] for row in cursor.fetchall()]

# ========== 项目级引用管理API ==========

@router.post("/v1/projects/{project_id}/document-references", 
            response_model=DocumentReferenceOperationResponse)
async def set_project_document_references(
    project_id: int = Path(...),
    request: ProjectDocumentReferencesRequest = Body(...)
):
    """
    设置项目级文档引用，完全替换现有引用
    """
    _validate_project_exists(project_id)
    _validate_documents_exist_in_project(request.document_ids, project_id)
    
    current_refs = set(_get_current_project_references(project_id))
    new_refs = set(request.document_ids)
    
    to_add = new_refs - current_refs
    to_remove = current_refs - new_refs
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 删除不再需要的引用
            if to_remove:
                placeholders = ','.join(['%s'] * len(to_remove))
                cursor.execute(
                    f"""DELETE FROM document_references 
                        WHERE project_id=%s AND reference_type='project' 
                        AND document_id IN ({placeholders})""",
                    tuple([project_id] + list(to_remove))
                )
            
            # 添加新的引用
            for doc_id in to_add:
                try:
                    cursor.execute(
                        """INSERT INTO document_references 
                           (project_id, document_id, reference_type) 
                           VALUES (%s, %s, 'project')""",
                        (project_id, doc_id)
                    )
                except Exception as e:
                    # 处理可能的重复键错误
                    if "Duplicate entry" not in str(e):
                        raise HTTPException(status_code=400, detail=f"Failed to add reference: {e}")
    
    return DocumentReferenceOperationResponse(
        message="Project document references updated successfully",
        added_count=len(to_add),
        removed_count=len(to_remove),
        current_references=sorted(request.document_ids)
    )

@router.delete("/v1/projects/{project_id}/document-references")
async def clear_project_document_references(project_id: int = Path(...)):
    """
    清空项目级文档引用
    """
    _validate_project_exists(project_id)
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM document_references WHERE project_id=%s AND reference_type='project'",
                (project_id,)
            )
            removed_count = cursor.rowcount
    
    return DocumentReferenceOperationResponse(
        message="All project document references cleared",
        added_count=0,
        removed_count=removed_count,
        current_references=[]
    )

# ========== 会话级引用管理API ==========

@router.post("/v1/chat/conversations/{conversation_id}/document-references", 
            response_model=DocumentReferenceOperationResponse)
async def set_conversation_document_references(
    conversation_id: str = Path(...),
    request: ConversationDocumentReferencesRequest = Body(...)
):
    """
    设置会话级文档引用，完全替换现有引用
    注意：会话只能引用其所属项目的文档，且不能引用项目级已引用的文档
    """
    project_id = _validate_conversation_exists(conversation_id)
    _validate_documents_exist_in_project(request.document_ids, project_id)
    
    # 检查是否有文档已被项目级引用
    project_refs = set(_get_current_project_references(project_id))
    conflicting_docs = set(request.document_ids) & project_refs
    if conflicting_docs:
        raise HTTPException(
            status_code=400,
            detail=f"Documents already referenced at project level: {sorted(conflicting_docs)}"
        )
    
    current_refs = set(_get_current_conversation_references(conversation_id))
    new_refs = set(request.document_ids)
    
    to_add = new_refs - current_refs
    to_remove = current_refs - new_refs
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 删除不再需要的引用
            if to_remove:
                placeholders = ','.join(['%s'] * len(to_remove))
                cursor.execute(
                    f"""DELETE FROM document_references 
                        WHERE conversation_id=%s AND reference_type='conversation' 
                        AND document_id IN ({placeholders})""",
                    tuple([conversation_id] + list(to_remove))
                )
            
            # 添加新的引用
            for doc_id in to_add:
                try:
                    cursor.execute(
                        """INSERT INTO document_references 
                           (project_id, conversation_id, document_id, reference_type) 
                           VALUES (%s, %s, %s, 'conversation')""",
                        (project_id, conversation_id, doc_id)
                    )
                except Exception as e:
                    # 处理可能的重复键错误
                    if "Duplicate entry" not in str(e):
                        raise HTTPException(status_code=400, detail=f"Failed to add reference: {e}")
    
    return DocumentReferenceOperationResponse(
        message="Conversation document references updated successfully",
        added_count=len(to_add),
        removed_count=len(to_remove),
        current_references=sorted(request.document_ids)
    )

@router.delete("/v1/chat/conversations/{conversation_id}/document-references")
async def clear_conversation_document_references(conversation_id: str = Path(...)):
    """
    清空会话级文档引用
    """
    _validate_conversation_exists(conversation_id)
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM document_references WHERE conversation_id=%s AND reference_type='conversation'",
                (conversation_id,)
            )
            removed_count = cursor.rowcount
    
    return DocumentReferenceOperationResponse(
        message="All conversation document references cleared",
        added_count=0,
        removed_count=removed_count,
        current_references=[]
    )