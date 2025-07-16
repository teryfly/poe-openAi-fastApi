from pydantic import BaseModel, field_validator
from typing import List, Optional, Union, Dict, Any
from enum import Enum
import json

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"

class FunctionCall(BaseModel):
    name: str
    arguments: str

class ToolCall(BaseModel):
    id: str
    type: str
    function: FunctionCall

class Function(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class Tool(BaseModel):
    type: str = "function"
    function: Function

def extract_all_content(data: Any) -> str:
    """递归提取所有内容，保留完整信息"""
    if isinstance(data, str):
        return data
    elif isinstance(data, dict):
        content_parts = []
        for key, value in data.items():
            if key == 'text' and isinstance(value, str):
                content_parts.append(value)
            elif key == 'content' and isinstance(value, str):
                content_parts.append(value)
            elif key in ['tool', 'function', 'tool_call', 'function_call'] and value:
                content_parts.append(f"[{key.upper()}: {json.dumps(value, ensure_ascii=False)}]")
            elif isinstance(value, (str, dict, list)):
                extracted = extract_all_content(value)
                if extracted:
                    content_parts.append(f"[{key.upper()}: {extracted}]")
        return ' '.join(content_parts)
    elif isinstance(data, list):
        content_parts = []
        for item in data:
            extracted = extract_all_content(item)
            if extracted:
                content_parts.append(extracted)
        return '\n'.join(content_parts)
    else:
        return str(data) if data else ""

class ChatMessage(BaseModel):
    role: Role
    content: Optional[Union[str, List[Any]]] = None
    name: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    
    @field_validator('content', mode='before')
    @classmethod
    def validate_content(cls, v):
        """验证并转换content格式，保留所有信息"""
        if v is None:
            return None
        if isinstance(v, str):
            return v
        elif isinstance(v, (list, dict)):
            return extract_all_content(v)
        else:
            return str(v) if v is not None else None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    functions: Optional[List[Function]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    logprobs: Optional[bool] = None
    top_logprobs: Optional[int] = None

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str
    logprobs: Optional[Dict[str, Any]] = None

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage
    system_fingerprint: Optional[str] = None

class ChatCompletionStreamChoice(BaseModel):
    index: int
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None
    logprobs: Optional[Dict[str, Any]] = None

class ChatCompletionStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionStreamChoice]
    system_fingerprint: Optional[str] = None

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str

class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]

class ErrorResponse(BaseModel):
    error: Dict[str, Any]