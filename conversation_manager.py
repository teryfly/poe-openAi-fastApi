import uuid
from threading import Lock

class ConversationManager:
    def __init__(self):
        self.conversations = {}
        self.lock = Lock()

    def create_conversation(self, system_prompt=None):
        conversation_id = str(uuid.uuid4())
        with self.lock:
            self.conversations[conversation_id] = []
            if system_prompt:
                self.conversations[conversation_id].append({
                    "role": "system",
                    "content": system_prompt
                })
        return conversation_id

    def append_message(self, conversation_id, role, content):
        with self.lock:
            if conversation_id not in self.conversations:
                raise KeyError("Conversation not found")
            self.conversations[conversation_id].append({
                "role": role,
                "content": content
            })

    def get_messages(self, conversation_id):
        with self.lock:
            if conversation_id not in self.conversations:
                raise KeyError("Conversation not found")
            return list(self.conversations[conversation_id])

    def clear(self):
        with self.lock:
            self.conversations.clear()

# 全局实例
conversation_manager = ConversationManager()