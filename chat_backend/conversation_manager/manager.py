import uuid
import pymysql
from threading import Lock
from datetime import datetime
from typing import Optional, List, Dict, Any

from db import get_conn
from .schema import ensure_conversation_tables
from .content import encode_content, normalize_message_row


class ConversationManager:
    def __init__(self):
        self.lock = Lock()
        ensure_conversation_tables()

    def _get_conn(self):
        return get_conn()

    def create_conversation(
        self,
        system_prompt: Optional[str] = None,
        project_id: int = 0,
        name: Optional[str] = None,
        model: Optional[str] = None,
        assistance_role: Optional[str] = None,
        status: int = 0,
    ) -> str:
        conversation_id = str(uuid.uuid4())
        now = datetime.now()
        with self.lock, self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO conversations
                        (id, system_prompt, status, created_at, updated_at, project_id, name, model, assistance_role)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (conversation_id, system_prompt, status, now, now, project_id, name, model, assistance_role),
                )
                if system_prompt:
                    cursor.execute(
                        "INSERT INTO messages (conversation_id, role, content, content_json, created_at) VALUES (%s, %s, %s, %s, %s)",
                        (conversation_id, "system", system_prompt, None, now),
                    )
        return conversation_id

    def update_conversation(self, conversation_id: str, project_id=None, name=None, model=None, assistance_role=None, status=None) -> bool:
        updates, values = [], []
        for col, val in [("project_id", project_id), ("name", name), ("model", model), ("assistance_role", assistance_role), ("status", status)]:
            if val is not None:
                updates.append(f"{col}=%s")
                values.append(val)
        updates.append("updated_at=%s")
        values.append(datetime.now())
        values.append(conversation_id)
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"UPDATE conversations SET {', '.join(updates)} WHERE id=%s", tuple(values))
                return cursor.rowcount > 0

    def get_conversation_by_id(self, conversation_id: str) -> Dict[str, Any]:
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT * FROM conversations WHERE id=%s", (conversation_id,))
                row = cursor.fetchone()
                if not row:
                    raise KeyError("Conversation not found")
                return row

    def get_conversations(self, project_id: Optional[int] = None, status: Optional[int] = None) -> List[Dict[str, Any]]:
        conds, vals = [], []
        if project_id is not None:
            conds.append("project_id=%s")
            vals.append(project_id)
        if status is not None:
            conds.append("status=%s")
            vals.append(status)
        where_clause = f"WHERE {' AND '.join(conds)}" if conds else ""
        sql = f"""SELECT id, system_prompt, status, created_at, updated_at, project_id, name, model, assistance_role
                  FROM conversations {where_clause} ORDER BY updated_at DESC, created_at DESC"""
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, tuple(vals))
                return list(cursor.fetchall())

    def get_all_conversations_grouped_by_project(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT c.id AS conversation_id, c.system_prompt, c.status, c.created_at, c.updated_at,
                           c.project_id, c.name, c.model, c.assistance_role, COALESCE(p.name, '其它') AS project_name
                    FROM conversations c
                    LEFT JOIN projects p ON c.project_id = p.id
                    ORDER BY c.updated_at DESC, c.created_at DESC
                    """
                )
                grouped: Dict[str, List[Dict[str, Any]]] = {}
                for row in cursor.fetchall():
                    grouped.setdefault(row["project_name"], []).append(row)
                return grouped

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM conversations WHERE id=%s", (conversation_id,))
                return cursor.rowcount > 0

    def append_message(self, conversation_id: str, role: str, content: Any, created_at: Optional[datetime] = None) -> int:
        created_at = created_at or datetime.now()
        content_text, content_json = encode_content(content)
        with self.lock, self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                if cursor.fetchone() is None:
                    raise KeyError("Conversation not found")
                cursor.execute(
                    "INSERT INTO messages (conversation_id, role, content, content_json, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (conversation_id, role, content_text, content_json or None, created_at),
                )
                msg_id = cursor.lastrowid
                cursor.execute("UPDATE conversations SET updated_at=%s WHERE id=%s", (datetime.now(), conversation_id))
                return msg_id

    def insert_assistant_placeholder(self, conversation_id: str, created_at: Optional[datetime] = None) -> int:
        return self.append_message(conversation_id, "assistant", "", created_at=created_at)

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                if cursor.fetchone() is None:
                    raise KeyError("Conversation not found")
                cursor.execute(
                    "SELECT id, role, content, content_json, created_at, updated_at FROM messages WHERE conversation_id=%s ORDER BY id ASC",
                    (conversation_id,),
                )
                return [normalize_message_row(r) for r in cursor.fetchall()]

    def delete_messages(self, message_ids: List[int]) -> int:
        if not message_ids:
            return 0
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                placeholders = ",".join(["%s"] * len(message_ids))
                cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", tuple(message_ids))
                return cursor.rowcount

    def update_message_content_and_time(self, message_id: int, content: Any, created_at: Optional[datetime] = None) -> bool:
        created_at = created_at or datetime.now()
        content_text, content_json = encode_content(content)
        with self.lock, self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE messages SET content=%s, content_json=%s, created_at=%s WHERE id=%s",
                    (content_text, content_json or None, created_at, message_id),
                )
                return cursor.rowcount > 0


conversation_manager = ConversationManager()