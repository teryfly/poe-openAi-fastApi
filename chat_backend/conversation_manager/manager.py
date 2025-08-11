import uuid
import pymysql
from threading import Lock
from datetime import datetime
from typing import Optional, List, Dict, Any
from db import get_conn
class ConversationManager:
    def __init__(self):
        self.lock = Lock()
        self._ensure_tables()
    def _get_conn(self):
        return get_conn()
    def _ensure_tables(self):
        """
        Ensure tables exist with latest schema:
        - conversations: +status, +updated_at, +project_id, +name, +assistance_role, +model
        - messages: MEDIUMTEXT content, +updated_at
        """
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id VARCHAR(64) PRIMARY KEY,
                        system_prompt MEDIUMTEXT,
                        status TINYINT NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        project_id INT NOT NULL DEFAULT 0,
                        name VARCHAR(32) DEFAULT NULL,
                        assistance_role VARCHAR(16) DEFAULT NULL,
                        model VARCHAR(64) DEFAULT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        conversation_id VARCHAR(64),
                        role VARCHAR(32),
                        content MEDIUMTEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    )
                """)
    # ---------- Conversations ----------
    def create_conversation(
        self,
        system_prompt: Optional[str] = None,
        project_id: int = 0,
        name: Optional[str] = None,
        model: Optional[str] = None,
        assistance_role: Optional[str] = None,
        status: int = 0
    ) -> str:
        """
        Create conversation and insert system prompt as system message (optional).
        Sets updated_at to now for immediate availability.
        """
        conversation_id = str(uuid.uuid4())
        now = datetime.now()
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO conversations
                            (id, system_prompt, status, created_at, updated_at, project_id, name, model, assistance_role)
                        VALUES
                            (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            conversation_id,
                            system_prompt,
                            status,
                            now,
                            now,
                            project_id,
                            name,
                            model,
                            assistance_role
                        )
                    )
                    if system_prompt:
                        cursor.execute(
                            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                            (conversation_id, "system", system_prompt, now)
                        )
        return conversation_id
    def update_conversation(
        self,
        conversation_id: str,
        project_id: Optional[int] = None,
        name: Optional[str] = None,
        model: Optional[str] = None,
        assistance_role: Optional[str] = None,
        status: Optional[int] = None
    ) -> bool:
        """
        Update fields for a conversation. Always updates updated_at to now.
        """
        updates: List[str] = []
        values: List[Any] = []
        if project_id is not None:
            updates.append("project_id=%s")
            values.append(project_id)
        if name is not None:
            updates.append("name=%s")
            values.append(name)
        if model is not None:
            updates.append("model=%s")
            values.append(model)
        if assistance_role is not None:
            updates.append("assistance_role=%s")
            values.append(assistance_role)
        if status is not None:
            updates.append("status=%s")
            values.append(status)
        # Always update the timestamp to maintain freshness
        updates.append("updated_at=%s")
        values.append(datetime.now())
        if not updates:
            return False
        values.append(conversation_id)
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                sql = f"UPDATE conversations SET {', '.join(updates)} WHERE id=%s"
                cursor.execute(sql, values)
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
        """
        List conversations optionally filtered by project_id and/or status.
        Ordered by updated_at DESC for recency.
        """
        conds: List[str] = []
        vals: List[Any] = []
        if project_id is not None:
            conds.append("project_id=%s")
            vals.append(project_id)
        if status is not None:
            conds.append("status=%s")
            vals.append(status)
        where_clause = f"WHERE {' AND '.join(conds)}" if conds else ""
        sql = f"""
            SELECT id, system_prompt, status, created_at, updated_at,
                   project_id, name, model, assistance_role
            FROM conversations
            {where_clause}
            ORDER BY updated_at DESC, created_at DESC
        """
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql, tuple(vals))
                return list(cursor.fetchall())
    def get_all_conversations_grouped_by_project(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Backward-compatible grouped listing with more fields (status, updated_at).
        """
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        c.id AS conversation_id,
                        c.system_prompt,
                        c.status,
                        c.created_at,
                        c.updated_at,
                        c.project_id,
                        c.name,
                        c.model,
                        c.assistance_role,
                        COALESCE(p.name, '其它') AS project_name
                    FROM conversations c
                    LEFT JOIN projects p ON c.project_id = p.id
                    ORDER BY c.updated_at DESC, c.created_at DESC
                """)
                rows = cursor.fetchall()
                grouped: Dict[str, List[Dict[str, Any]]] = {}
                for row in rows:
                    pname = row["project_name"]
                    grouped.setdefault(pname, []).append(row)
                return grouped
    def delete_conversation(self, conversation_id: str) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM conversations WHERE id=%s", (conversation_id,))
                return cursor.rowcount > 0
    def clear(self):
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM messages")
                    cursor.execute("DELETE FROM conversations")
    # ---------- Messages ----------
    def append_message(self, conversation_id: str, role: str, content: str, created_at: Optional[datetime] = None) -> int:
        """
        Insert a message and bump the parent conversation's updated_at to now.
        Returns the inserted message id.
        """
        created_at = created_at or datetime.now()
        now = datetime.now()
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                    if cursor.fetchone() is None:
                        raise KeyError("Conversation not found")
                    cursor.execute(
                        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                        (conversation_id, role, content, created_at)
                    )
                    msg_id = cursor.lastrowid
                    # bump conversation updated_at
                    cursor.execute("UPDATE conversations SET updated_at=%s WHERE id=%s", (now, conversation_id))
                    return msg_id
    def insert_assistant_placeholder(self, conversation_id: str, created_at: Optional[datetime] = None) -> int:
        """
        Insert a placeholder assistant message (empty content) and bump conversation updated_at.
        Returns the inserted message ID.
        """
        created_at = created_at or datetime.now()
        now = datetime.now()
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                    if cursor.fetchone() is None:
                        raise KeyError("Conversation not found")
                    cursor.execute(
                        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                        (conversation_id, "assistant", "", created_at)
                    )
                    msg_id = cursor.lastrowid
                    cursor.execute("UPDATE conversations SET updated_at=%s WHERE id=%s", (now, conversation_id))
                    return msg_id
    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                    if cursor.fetchone() is None:
                        raise KeyError("Conversation not found")
                    cursor.execute(
                        "SELECT id, role, content, created_at, updated_at FROM messages WHERE conversation_id=%s ORDER BY id ASC",
                        (conversation_id,)
                    )
                    return list(cursor.fetchall())
    def delete_messages(self, message_ids: List[int]) -> int:
        """Delete one or more messages by ids."""
        if not message_ids:
            return 0
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(message_ids))
                cursor.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", tuple(message_ids))
                return cursor.rowcount
    def update_message_content_and_time(self, message_id: int, content: str, created_at: Optional[datetime] = None) -> bool:
        """
        Update specific message content and optionally its created_at.
        updated_at is auto-managed by MySQL ON UPDATE.
        """
        if created_at is None:
            created_at = datetime.now()
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE messages SET content=%s, created_at=%s WHERE id=%s",
                        (content, created_at, message_id)
                    )
                    return cursor.rowcount > 0
# Global instance (backward compatible import)
conversation_manager = ConversationManager()