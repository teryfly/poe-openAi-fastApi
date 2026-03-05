from db import get_conn


def ensure_conversation_tables() -> None:
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
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
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    conversation_id VARCHAR(64),
                    role VARCHAR(32),
                    content MEDIUMTEXT,
                    content_json JSON NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
                """
            )
            _ensure_column(cursor, "messages", "content_json", "ALTER TABLE messages ADD COLUMN content_json JSON NULL")


def _ensure_column(cursor, table_name: str, column_name: str, ddl_sql: str) -> None:
    cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
    if cursor.fetchone() is None:
        cursor.execute(ddl_sql)