import uuid
import pymysql
from threading import Lock
from datetime import datetime

# 数据库配置，可根据实际情况外部导入
db_config = {
    "host": "localhost",
    "port": 3306,
    "user": "sa",
    "password": "dm257758",
    "database": "plan_manager",
    "charset": "utf8mb4",
    "autocommit": True,
    "connect_timeout": 5
}

class ConversationManager:
    def __init__(self):
        self.lock = Lock()
        self._ensure_tables()

    def _get_conn(self):
        return pymysql.connect(**db_config)

    def _ensure_tables(self):
        with self._get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id VARCHAR(64) PRIMARY KEY,
                        system_prompt TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

    def create_conversation(self, system_prompt=None):
        conversation_id = str(uuid.uuid4())
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO conversations (id, system_prompt, created_at) VALUES (%s, %s, %s)",
                        (conversation_id, system_prompt, datetime.now())
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
                    # 检查会话是否存在
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

    def clear(self):
        with self.lock:
            with self._get_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM messages")
                    cursor.execute("DELETE FROM conversations")

# 全局实例
conversation_manager = ConversationManager()