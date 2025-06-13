import json
import os
from datetime import datetime
from typing import Any, Dict
import asyncio
from threading import Lock

class RequestLogger:
    def __init__(self, log_dir: str = "train_data"):
        self.log_dir = log_dir
        self.file_lock = Lock()
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_log_filename(self) -> str:
        """获取基于日期的日志文件名"""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{today}.jsonl")
    
    def log_request_response(self, request_data: Dict[str, Any], response_data: Dict[str, Any], 
                           response_time: float):
        """记录请求和响应"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request": request_data,
            "response": response_data,
            "response_time_ms": round(response_time * 1000, 2)
        }
        
        filename = self._get_log_filename()
        
        # 使用线程锁确保文件写入安全
        with self.file_lock:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    def log_stream_request_response(self, request_data: Dict[str, Any], 
                                  full_response: str, response_time: float):
        """记录流式请求的完整响应"""
        response_data = {
            "stream": True,
            "full_content": full_response,
            "content_length": len(full_response)
        }
        self.log_request_response(request_data, response_data, response_time)

# 全局日志实例
request_logger = RequestLogger()