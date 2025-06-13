#!/usr/bin/env python3
"""
启动脚本
"""
import os
import sys
import uvicorn

def main():
    """主启动函数"""
    print("🔧 正在启动OpenAI兼容API代理服务...")
    
    # 创建日志目录
    from config import Config
    os.makedirs(Config.LOG_DIR, exist_ok=True)
    
    # 启动服务
    uvicorn.run(
        "main:app",  # 使用字符串导入，避免循环导入
        host=Config.HOST,
        port=Config.PORT,
        log_level="info",
        access_log=True,
        reload=True
    )

if __name__ == "__main__":
    main()