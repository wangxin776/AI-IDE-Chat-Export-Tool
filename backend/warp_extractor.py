"""
Warp AI 数据提取器 - 集成到 AI-IDE-Chat-Export-Tool 项目

这个模块负责从 Warp Terminal 的数据库中提取 AI 对话数据，
并将其转换为与现有项目兼容的格式。
"""

import json
import logging
import sqlite3
import platform
import pathlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 导入增强的对话解析器
from conversation_parser import ConversationParser

logger = logging.getLogger(__name__)

@dataclass
class WarpMessage:
    """Warp 消息数据类"""
    role: str
    content: str
    timestamp: datetime
    exchange_id: str

@dataclass
class WarpConversation:
    """Warp 对话数据类"""
    id: str
    created_at: datetime
    last_interacted_at: datetime
    messages: List[WarpMessage]
    working_directory: str = None
    model_id: str = None
    metadata: Dict[str, Any] = None

class WarpDataExtractor:
    """Warp 数据提取器，集成到 AI-IDE-Chat-Export-Tool 架构中"""
    
    def __init__(self, custom_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.conversation_parser = ConversationParser()
        self.custom_path = custom_path
    
    def get_storage_path(self) -> Optional[pathlib.Path]:
        """
        获取 Warp 的数据库路径
        优先使用自定义路径，如果未设置则使用默认路径

        Returns:
            Warp 数据库路径或 None
        """
        try:
            # 如果设置了自定义路径，优先使用
            if self.custom_path:
                custom_path_obj = pathlib.Path(self.custom_path)
                if custom_path_obj.exists():
                    self.logger.info(f"使用自定义 Warp 路径: {self.custom_path}")
                    return custom_path_obj
                else:
                    self.logger.warning(f"自定义 Warp 路径不存在: {self.custom_path}，回退到默认路径")

            # 使用默认路径
            home = pathlib.Path.home()
            system = platform.system()

            if system == "Darwin":  # macOS
                warp_path = home / "Library" / "Group Containers" / "2BBY89MBSN.dev.warp" / "Library" / "Application Support" / "dev.warp.Warp-Stable" / "warp.sqlite"
            elif system == "Windows":
                # Warp 目前主要支持 macOS，Windows 路径可能不同
                self.logger.warning(f"Warp 在 Windows 上的支持有限")
                return None
            elif system == "Linux":
                # Warp Linux 版本路径（假设）
                warp_path = home / ".local" / "share" / "warp-terminal" / "warp.sqlite"
            else:
                self.logger.warning(f"不支持的操作系统: {system}")
                return None

            if warp_path.exists():
                self.logger.info(f"使用默认 Warp 数据库路径: {warp_path}")
                return warp_path
            else:
                self.logger.warning(f"Warp 数据库路径不存在: {warp_path}")
                return None

        except Exception as e:
            self.logger.error(f"获取 Warp 存储路径失败: {e}")
            return None
    
    def _parse_query_input(self, input_json: List[Dict]) -> tuple[str, Dict[str, Any]]:
        """
        解析用户查询输入数据
        
        Args:
            input_json: 输入 JSON 数据
            
        Returns:
            (用户查询文本, 上下文信息)
        """
        user_query = ""
        context_info = {}
        
        for item in input_json:
            if "Query" in item:
                user_query = item["Query"].get("text", "")
                # 提取上下文信息
                context = item["Query"].get("context", [])
                for ctx in context:
                    if "Directory" in ctx:
                        context_info["directory"] = ctx["Directory"]
                    elif "CurrentTime" in ctx:
                        context_info["time"] = ctx["CurrentTime"]
                    elif "SelectedText" in ctx:
                        context_info["selected_text"] = ctx["SelectedText"]
                    elif "ProjectRules" in ctx:
                        context_info["project_rules"] = ctx["ProjectRules"]
        
        return user_query, context_info
    
    def _parse_response_output(self, output_json: Dict) -> str:
        """
        解析助手回复输出数据
        
        Args:
            output_json: 输出 JSON 数据
            
        Returns:
            助手回复文本
        """
        assistant_response = ""
        
        if "Received" in output_json:
            outputs = output_json["Received"].get("output", [])
            texts = []
            for out in outputs:
                if "Text" in out:
                    texts.append(out["Text"].get("text", ""))
            assistant_response = "\n".join(texts)
        
        return assistant_response
    
    def extract_warp_conversations(self) -> List[WarpConversation]:
        """
        提取所有 Warp AI 对话数据
        
        Returns:
            Warp 对话列表
        """
        db_path = self.get_storage_path()
        if not db_path:
            self.logger.warning("未找到 Warp 数据库")
            return []
        
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            
            # 获取所有对话的交互记录
            cursor.execute("""
                SELECT 
                    q.conversation_id,
                    q.exchange_id,
                    q.start_ts,
                    q.input,
                    q.working_directory,
                    q.model_id,
                    b.output
                FROM ai_queries q
                LEFT JOIN ai_blocks b ON q.exchange_id = b.exchange_id
                ORDER BY q.conversation_id, q.start_ts
            """)
            
            # 按对话 ID 组织数据
            conversations_data = {}
            for row in cursor.fetchall():
                conv_id, exchange_id, start_ts, input_data, work_dir, model_id, output_data = row
                
                if conv_id not in conversations_data:
                    conversations_data[conv_id] = {
                        "messages": [],
                        "working_directory": work_dir,
                        "model_id": model_id,
                        "first_timestamp": start_ts,
                        "last_timestamp": start_ts
                    }
                
                # 更新最后时间戳
                conversations_data[conv_id]["last_timestamp"] = start_ts
                
                try:
                    input_json = json.loads(input_data) if input_data else []
                    output_json = json.loads(output_data) if output_data else {}
                    
                    # 解析用户查询
                    user_query, context_info = self._parse_query_input(input_json)
                    
                    if user_query:
                        # 添加用户消息
                        conversations_data[conv_id]["messages"].append(
                            WarpMessage(
                                role="user",
                                content=user_query,
                                timestamp=datetime.fromisoformat(start_ts.replace("Z", "+00:00")) if start_ts else datetime.now(),
                                exchange_id=exchange_id
                            )
                        )
                    
                    # 解析助手回复
                    assistant_response = self._parse_response_output(output_json)
                    
                    if assistant_response:
                        # 添加助手消息
                        conversations_data[conv_id]["messages"].append(
                            WarpMessage(
                                role="assistant",
                                content=assistant_response,
                                timestamp=datetime.fromisoformat(start_ts.replace("Z", "+00:00")) if start_ts else datetime.now(),
                                exchange_id=exchange_id
                            )
                        )
                
                except json.JSONDecodeError as e:
                    self.logger.warning(f"解析交互 {exchange_id} 失败: {e}")
                    continue
            
            # 获取对话元数据
            cursor.execute("""
                SELECT conversation_id, conversation_data, last_modified_at
                FROM agent_conversations
            """)
            
            metadata_map = {}
            for row in cursor.fetchall():
                conv_id, conv_data, modified_at = row
                try:
                    metadata_map[conv_id] = {
                        "last_modified": modified_at,
                        "data": json.loads(conv_data) if conv_data else {}
                    }
                except json.JSONDecodeError:
                    pass
            
            conn.close()
            
            # 转换为 WarpConversation 对象
            conversations = []
            for conv_id, data in conversations_data.items():
                if not data["messages"]:
                    continue
                
                metadata = metadata_map.get(conv_id, {})
                
                conversations.append(
                    WarpConversation(
                        id=conv_id,
                        created_at=datetime.fromisoformat(data["first_timestamp"].replace("Z", "+00:00")) if data["first_timestamp"] else datetime.now(),
                        last_interacted_at=datetime.fromisoformat(data["last_timestamp"].replace("Z", "+00:00")) if data["last_timestamp"] else datetime.now(),
                        messages=data["messages"],
                        working_directory=data.get("working_directory"),
                        model_id=data.get("model_id"),
                        metadata=metadata
                    )
                )
            
            self.logger.info(f"成功提取 {len(conversations)} 个 Warp 对话")
            return conversations
        
        except Exception as e:
            self.logger.error(f"提取 Warp 对话失败: {e}")
            return []
    
    def convert_to_cursor_view_format(self, conversations: List[WarpConversation]) -> List[Dict[str, Any]]:
        """
        将 Warp 对话转换为 cursor-view 兼容格式
        
        Args:
            conversations: Warp 对话列表
            
        Returns:
            cursor-view 格式的对话列表
        """
        cursor_format_chats = []
        
        for conv in conversations:
            if not conv.messages:
                continue
            
            # 提取项目名称
            project_name = "Unknown Project"
            if conv.working_directory:
                try:
                    path_parts = pathlib.Path(conv.working_directory).parts
                    # 获取最后一个有意义的目录名
                    for part in reversed(path_parts):
                        if part and part not in [".", "..", "~"]:
                            project_name = part
                            break
                except Exception:
                    pass
            
            # 生成对话标题
            title = f"Warp Chat"
            if conv.messages:
                # 使用第一条用户消息作为标题
                first_user_msg = next((msg for msg in conv.messages if msg.role == "user"), None)
                if first_user_msg and first_user_msg.content:
                    title = first_user_msg.content[:50] + ("..." if len(first_user_msg.content) > 50 else "")
            
            # 转换消息格式
            messages = []
            for msg in conv.messages:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 构建 cursor-view 格式的对话对象
            chat = {
                "id": conv.id,
                "title": title,
                "project": project_name,
                "working_directory": conv.working_directory,
                "model_id": conv.model_id or "claude-4.5-sonnet",
                "createdAt": conv.created_at.isoformat() if conv.created_at else None,
                "lastUpdatedAt": conv.last_interacted_at.isoformat() if conv.last_interacted_at else None,
                "messages": messages,
                "metadata": conv.metadata,
                "source": "warp"  # 标识数据来源
            }
            
            cursor_format_chats.append(chat)
        
        self.logger.info(f"成功转换 {len(cursor_format_chats)} 个对话为 cursor-view 格式")
        return cursor_format_chats
