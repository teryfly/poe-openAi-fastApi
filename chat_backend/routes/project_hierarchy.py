from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from db import get_conn

router = APIRouter()


class ReferencedDocumentItem(BaseModel):
    document_id: int
    filename: str
    version: Optional[int] = None


class ConversationHierarchyItem(BaseModel):
    id: str
    name: Optional[str] = None
    model: Optional[str] = None
    assistance_role: Optional[str] = None
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    conversation_document_references: List[ReferencedDocumentItem]


class ProjectConversationReferenceHierarchyResponse(BaseModel):
    project_id: int
    project_name: str
    project_document_references: List[ReferencedDocumentItem]
    conversations: List[ConversationHierarchyItem]


def _row_to_dict(cursor, row) -> Dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def _append_unique_ref(
    target: List[ReferencedDocumentItem],
    seen: Set[Tuple[int, str, Optional[int]]],
    document_id: int,
    filename: str,
    version: Optional[int],
) -> None:
    key = (document_id, filename, version)
    if key in seen:
        return
    seen.add(key)
    target.append(
        ReferencedDocumentItem(
            document_id=document_id,
            filename=filename,
            version=version,
        )
    )


@router.get(
    "/v1/projects/{project_id}/hierarchy",
    response_model=ProjectConversationReferenceHierarchyResponse,
)
async def get_project_conversation_reference_hierarchy(project_id: int = Path(...)):
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # 1) project basic info
            cursor.execute("SELECT id, name FROM projects WHERE id=%s", (project_id,))
            project_row = cursor.fetchone()
            if not project_row:
                raise HTTPException(status_code=404, detail="Project not found")
            project = _row_to_dict(cursor, project_row)

            # 2) conversations under project
            cursor.execute(
                """
                SELECT id, name, model, assistance_role, status, created_at, updated_at
                FROM conversations
                WHERE project_id=%s
                ORDER BY updated_at DESC, created_at DESC
                """,
                (project_id,),
            )
            conversation_rows = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

            # 3) all references (project-level + conversation-level) in one query
            cursor.execute(
                """
                SELECT
                    dr.reference_type,
                    dr.conversation_id,
                    dr.document_id,
                    pd.filename,
                    pd.version
                FROM document_references dr
                JOIN plan_documents pd ON pd.id = dr.document_id
                WHERE dr.project_id=%s
                  AND (
                        dr.reference_type='project'
                        OR (dr.reference_type='conversation' AND dr.conversation_id IS NOT NULL)
                  )
                ORDER BY dr.reference_type ASC, dr.conversation_id ASC, pd.filename ASC, pd.version DESC
                """,
                (project_id,),
            )
            reference_rows = [_row_to_dict(cursor, r) for r in cursor.fetchall()]

    # Build project-level refs
    project_document_references: List[ReferencedDocumentItem] = []
    seen_project_refs: Set[Tuple[int, str, Optional[int]]] = set()

    # Build conversation-level refs map
    conversation_ref_map: Dict[str, List[ReferencedDocumentItem]] = {}
    seen_conversation_refs: Dict[str, Set[Tuple[int, str, Optional[int]]]] = {}

    for row in reference_rows:
        ref_type = row.get("reference_type")
        doc_id = int(row.get("document_id"))
        filename = str(row.get("filename") or "")
        version = row.get("version")

        if ref_type == "project":
            _append_unique_ref(
                target=project_document_references,
                seen=seen_project_refs,
                document_id=doc_id,
                filename=filename,
                version=version,
            )
            continue

        conv_id = row.get("conversation_id")
        if not conv_id:
            continue

        if conv_id not in conversation_ref_map:
            conversation_ref_map[conv_id] = []
            seen_conversation_refs[conv_id] = set()

        _append_unique_ref(
            target=conversation_ref_map[conv_id],
            seen=seen_conversation_refs[conv_id],
            document_id=doc_id,
            filename=filename,
            version=version,
        )

    conversations: List[ConversationHierarchyItem] = []
    for convo in conversation_rows:
        cid = str(convo.get("id"))
        conversations.append(
            ConversationHierarchyItem(
                id=cid,
                name=convo.get("name"),
                model=convo.get("model"),
                assistance_role=convo.get("assistance_role"),
                status=int(convo.get("status") or 0),
                created_at=convo.get("created_at"),
                updated_at=convo.get("updated_at"),
                conversation_document_references=conversation_ref_map.get(cid, []),
            )
        )

    return ProjectConversationReferenceHierarchyResponse(
        project_id=int(project.get("id")),
        project_name=str(project.get("name") or ""),
        project_document_references=project_document_references,
        conversations=conversations,
    )