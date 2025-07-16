import asyncio
import fastapi_poe as fp
from typing import AsyncGenerator, List
from config import Config
import logging

logger = logging.getLogger(__name__)

class PoeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @staticmethod
    def convert_role_to_poe(role: str) -> str:
        """将OpenAI角色格式转换为Poe格式"""
        role_mapping = {
            'system': 'system',
            'user': 'user', 
            'assistant': 'bot',
            'tool': 'user',
            'function': 'user'
        }
        return role_mapping.get(role.lower(), 'user')
    
    async def get_response_stream(self, messages: List[dict], model: str) -> AsyncGenerator[str, None]:
        """获取Poe的流式响应 - 直接使用Poe模型名称"""
        try:
            poe_messages = []
            
            for i, msg in enumerate(messages):
                # 转换角色格式
                poe_role = self.convert_role_to_poe(msg["role"])
                
                # 处理content
                content = msg.get("content", "")
                if isinstance(content, list):
                    # 如果是列表格式，提取text内容
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
                    content = "\n".join(text_parts)
                
                if content and str(content).strip():  # 只有非空内容才添加
                    poe_messages.append(
                        fp.ProtocolMessage(role=poe_role, content=str(content))
                    )
                    logger.info(f"Message {i}: {msg['role']} -> {poe_role} (length: {len(str(content))})")
            
            logger.info(f"Using Poe model: {model}")
            logger.info(f"Sending {len(poe_messages)} messages to Poe")
            
            async for partial in fp.get_bot_response(
                messages=poe_messages,
                bot_name=model,  # 直接使用Poe模型名称
                api_key=self.api_key
            ):
                if hasattr(partial, 'text') and partial.text:
                    yield partial.text
                    
        except Exception as e:
            logger.error(f"Error getting Poe response: {e}")
            logger.error(f"Model: {model}")
            logger.error(f"Messages sent: {[{'role': msg['role'], 'content_preview': str(msg.get('content', ''))[:100]} for msg in messages]}")
            yield f"Error: {str(e)}"
    
    async def get_response_complete(self, messages: List[dict], model: str) -> str:
        """获取Poe的完整响应"""
        full_response = ""
        async for chunk in self.get_response_stream(messages, model):
            full_response += chunk
        return full_response