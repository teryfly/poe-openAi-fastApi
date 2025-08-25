from fastapi import APIRouter, HTTPException, Body, Path, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from db import get_conn
from datetime import datetime

router = APIRouter()

# ========== 数据模型 ==========

class DocumentReferenceResponse(BaseModel):
    id: int
    project_id: int
    conversation_id: Optional[str]
    document_id: int
    reference_type: str
    document_filename: Optional[str] = None
    document_content: Optional[str] = None
    document_version: Optional[int] = None
    document_created_time: Optional[str] = None

class ProjectDocumentReferencesRequest(BaseModel):
    document_ids: List[int]

class ConversationDocumentReferencesRequest(BaseModel):
    document_ids: List[int]

class ConversationReferencedDocumentsResponse(BaseModel):
    conversation_id: str
    project_references: List[DocumentReferenceResponse]
    conversation_references: List[DocumentReferenceResponse]

# ========== 工具函数 ==========

def _row_to_dict(cursor, row):
    """将数据库行转换为字典"""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))

def _format_datetime(dt):
    """格式化datetime对象为ISO字符串"""
    if dt and isinstance(dt, datetime):
        return dt.isoformat()
    return dt

# ========== 查询API ==========

@router.get("/v1/chat/conversations/{conversation_id}/referenced-documents", 
           response_model=ConversationReferencedDocumentsResponse)
async def get_conversation_referenced_documents(conversation_id: str = Path(...)):
    """
    查询会话引用的文档列表，分为项目级引用和会话级引用
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 先查询会话所属的项目ID
            cursor.execute("SELECT project_id FROM conversations WHERE id=%s", (conversation_id,))
            conv_row = cursor.fetchone()
            if not conv_row:
                raise HTTPException(status_code=404, detail="Conversation not found")
            
            project_id = conv_row[0]
            
            # 查询项目级引用
            cursor.execute("""
                SELECT 
                    dr.id, dr.project_id, dr.conversation_id, dr.document_id, dr.reference_type,
                    pd.filename, pd.content, pd.version, pd.created_time
                FROM document_references dr
                LEFT JOIN plan_documents pd ON dr.document_id = pd.id
                WHERE dr.project_id = %s AND dr.reference_type = 'project'
                ORDER BY pd.filename ASC
            """, (project_id,))
            
            project_refs = []
            for row in cursor.fetchall():
                ref_dict = _row_to_dict(cursor, row)
                project_refs.append(DocumentReferenceResponse(
                    id=ref_dict['id'],
                    project_id=ref_dict['project_id'],
                    conversation_id=ref_dict['conversation_id'],
                    document_id=ref_dict['document_id'],
                    reference_type=ref_dict['reference_type'],
                    document_filename=ref_dict['filename'],
                    document_content=ref_dict['content'],
                    document_version=ref_dict['version'],
                    document_created_time=_format_datetime(ref_dict['created_time'])
                ))
            
            # 查询会话级引用
            cursor.execute("""
                SELECT 
                    dr.id, dr.project_id, dr.conversation_id, dr.document_id, dr.reference_type,
                    pd.filename, pd.content, pd.version, pd.created_time
                FROM document_references dr
                LEFT JOIN plan_documents pd ON dr.document_id = pd.id
                WHERE dr.conversation_id = %s AND dr.reference_type = 'conversation'
                ORDER BY pd.filename ASC
            """, (conversation_id,))
            
            conversation_refs = []
            for row in cursor.fetchall():
                ref_dict = _row_to_dict(cursor, row)
                conversation_refs.append(DocumentReferenceResponse(
                    id=ref_dict['id'],
                    project_id=ref_dict['project_id'],
                    conversation_id=ref_dict['conversation_id'],
                    document_id=ref_dict['document_id'],
                    reference_type=ref_dict['reference_type'],
                    document_filename=ref_dict['filename'],
                    document_content=ref_dict['content'],
                    document_version=ref_dict['version'],
                    document_created_time=_format_datetime(ref_dict['created_time'])
                ))
            
            return ConversationReferencedDocumentsResponse(
                conversation_id=conversation_id,
                project_references=project_refs,
                conversation_references=conversation_refs
            )

@router.get("/v1/projects/{project_id}/document-references", 
           response_model=List[DocumentReferenceResponse])
async def get_project_document_references(project_id: int = Path(...)):
    """
    查询项目级文档引用列表
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    dr.id, dr.project_id, dr.conversation_id, dr.document_id, dr.reference_type,
                    pd.filename, pd.content, pd.version, pd.created_time
                FROM document_references dr
                LEFT JOIN plan_documents pd ON dr.document_id = pd.id
                WHERE dr.project_id = %s AND dr.reference_type = 'project'
                ORDER BY pd.filename ASC
            """, (project_id,))
            
            references = []
            for row in cursor.fetchall():
                ref_dict = _row_to_dict(cursor, row)
                references.append(DocumentReferenceResponse(
                    id=ref_dict['id'],
                    project_id=ref_dict['project_id'],
                    conversation_id=ref_dict['conversation_id'],
                    document_id=ref_dict['document_id'],
                    reference_type=ref_dict['reference_type'],
                    document_filename=ref_dict['filename'],
                    document_content=ref_dict['content'],
                    document_version=ref_dict['version'],
                    document_created_time=_format_datetime(ref_dict['created_time'])
                ))
            
            return references

@router.get("/v1/chat/conversations/{conversation_id}/document-references", 
           response_model=List[DocumentReferenceResponse])
async def get_conversation_document_references(conversation_id: str = Path(...)):
    """
    查询会话级文档引用列表
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    dr.id, dr.project_id, dr.conversation_id, dr.document_id, dr.reference_type,
                    pd.filename, pd.content, pd.version, pd.created_time
                FROM document_references dr
                LEFT JOIN plan_documents pd ON dr.document_id = pd.id
                WHERE dr.conversation_id = %s AND dr.reference_type = 'conversation'
                ORDER BY pd.filename ASC
            """, (conversation_id,))
            
            references = []
            for row in cursor.fetchall():
                ref_dict = _row_to_dict(cursor, row)
                references.append(DocumentReferenceResponse(
                    id=ref_dict['id'],
                    project_id=ref_dict['project_id'],
                    conversation_id=ref_dict['conversation_id'],
                    document_id=ref_dict['document_id'],
                    reference_type=ref_dict['reference_type'],
                    document_filename=ref_dict['filename'],
                    document_content=ref_dict['content'],
                    document_version=ref_dict['version'],
                    document_created_time=_format_datetime(ref_dict['created_time'])
                ))
            
            return references