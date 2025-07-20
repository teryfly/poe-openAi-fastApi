import uuid
import pymysql
from threading import Lock
from datetime import datetime
from db import get_conn

class ConversationManager:
    def __init__(self):
        self.lock = Lock()
        self._ensure_tables()

    def _get_conn(self):
        return get_conn()


    def _ensure_tables(self):
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id VARCHAR(64) PRIMARY KEY,
                        system_prompt TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        project_id INT NOT NULL DEFAULT 0,
                        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET DEFAULT
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        conversation_id VARCHAR(64),
                        role VARCHAR(32),
                        content TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    )
                """)

    def create_conversation(self, system_prompt=None, project_id=0, name=None, model=None, assistance_role=None):
        conversation_id = str(uuid.uuid4())
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO conversations (id, system_prompt, created_at, project_id, name, model, assistance_role) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (conversation_id, system_prompt, datetime.now(), project_id, name, model, assistance_role)
                    )
                    if system_prompt:
                        cursor.execute(
                            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                            (conversation_id, "system", system_prompt, datetime.now())
                        )
        return conversation_id

    def append_message(self, conversation_id, role, content):
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                    if cursor.fetchone() is None:
                        raise KeyError("Conversation not found")
                    cursor.execute(
                        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
                        (conversation_id, role, content, datetime.now())
                    )

    def get_messages(self, conversation_id):
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute("SELECT 1 FROM conversations WHERE id=%s", (conversation_id,))
                    if cursor.fetchone() is None:
                        raise KeyError("Conversation not found")
                    cursor.execute(
                        "SELECT role, content FROM messages WHERE conversation_id=%s ORDER BY id ASC",
                        (conversation_id,)
                    )
                    return list(cursor.fetchall())

    def get_all_conversations_grouped_by_project(self):
        with self._get_conn() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        c.id AS conversation_id, c.system_prompt, c.created_at, c.project_id,
                        c.name, c.model, c.assistance_role,
                        COALESCE(p.name, '其它') AS project_name
                    FROM conversations c
                    LEFT JOIN projects p ON c.project_id = p.id
                    ORDER BY c.created_at DESC
                """)
                rows = cursor.fetchall()
                grouped = {}
                for row in rows:
                    pname = row["project_name"]
                    grouped.setdefault(pname, []).append(row)
                return grouped

    def update_conversation(self, conversation_id, project_id=None, name=None, model=None, assistance_role=None):
        updates = []
        values = []
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
        if not updates:
            return False
        values.append(conversation_id)
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                sql = f"UPDATE conversations SET {', '.join(updates)} WHERE id=%s"
                cursor.execute(sql, values)
                return cursor.rowcount > 0


    def delete_conversation(self, conversation_id):
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

    def append_message(self, conversation_id, role, content, created_at=None):
        from datetime import datetime
        created_at = created_at or datetime.now()
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

    def append_message_returning_id(self, conversation_id, role, content, created_at=None):
        # 用于流式助手占位符消息
        from datetime import datetime
        created_at = created_at or datetime.now()
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
                    return cursor.lastrowid
    def insert_assistant_placeholder(self, conversation_id, created_at=None):
        """
        插入一条占位符消息（role=assistant，content为空字符串）
        返回插入的消息ID
        """
        if created_at is None:
            created_at = datetime.now()
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
                    return cursor.lastrowid

    def update_message_content_and_time(self, message_id, content, created_at=None):
        """
        更新指定消息的内容和（可选）创建时间
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
# 全局实例
conversation_manager = ConversationManager()
