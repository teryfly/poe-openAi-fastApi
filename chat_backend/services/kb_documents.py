from typing import List, Optional
from db import get_conn
from conversation_manager import conversation_manager


def build_kb_block_from_documents(doc_ids: List[int]) -> Optional[str]:
    if not doc_ids:
        return None

    placeholders = ",".join(["%s"] * len(doc_ids))
    sql = f"""
        SELECT id, filename, content
        FROM plan_documents
        WHERE id IN ({placeholders})
        ORDER BY FIELD(id, {placeholders})
    """
    params = tuple(doc_ids + doc_ids)

    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                return None
            cols = [c[0] for c in cursor.description]
            parts = []
            for row in rows:
                rec = dict(zip(cols, row))
                title = (rec.get("filename") or "").strip() or f"document_{rec.get('id')}"
                body = rec.get("content") or ""
                parts.append(f"----- {title} BEGINE -----\n{body}\n----- {title} END -----")
            return "\n\n".join(parts)


def inject_kb_into_system_prompt(conversation_id: str, kb_block: Optional[str]) -> Optional[str]:
    convo = conversation_manager.get_conversation_by_id(conversation_id)
    original = (convo.get("system_prompt") or "").strip()
    if not kb_block:
        return original or None
    if original:
        return f"{original}\n\n{kb_block}"
    return kb_block