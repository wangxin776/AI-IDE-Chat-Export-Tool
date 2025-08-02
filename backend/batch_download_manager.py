#!/usr/bin/env python3
"""
批量下载管理器
负责管理批量下载任务的创建、执行、状态跟踪和取消操作
"""

import json
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import tempfile
import os

# 注意：避免循环导入，这些函数将在运行时动态导入


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchTaskInfo:
    """批量任务信息"""
    task_id: str
    session_ids: List[str]
    format_type: str
    source: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    completed_count: int = 0
    total_count: int = 0
    error_message: Optional[str] = None
    output_file_path: Optional[str] = None
    failed_sessions: List[str] = None
    
    def __post_init__(self):
        if self.failed_sessions is None:
            self.failed_sessions = []
        self.total_count = len(self.session_ids)


class BatchDownloadManager:
    """批量下载管理器"""
    
    def __init__(self, max_workers: int = 5, max_concurrent_tasks: int = 3):
        """
        初始化批量下载管理器
        
        Args:
            max_workers: 单个任务的最大并发工作线程数
            max_concurrent_tasks: 最大并发任务数
        """
        self.max_workers = max_workers
        self.max_concurrent_tasks = max_concurrent_tasks
        self.tasks: Dict[str, BatchTaskInfo] = {}
        self.active_tasks: Dict[str, threading.Thread] = {}
        self.task_lock = threading.Lock()
        self.temp_dir = Path(tempfile.gettempdir()) / "ai_ide_batch_downloads"
        self.temp_dir.mkdir(exist_ok=True)
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 启动清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_tasks, daemon=True)
        self.cleanup_thread.start()
    
    def create_batch_task(self, session_ids: List[str], format_type: str, source: str) -> str:
        """
        创建批量下载任务
        
        Args:
            session_ids: 要下载的会话ID列表
            format_type: 导出格式 ('html', 'json', 'markdown')
            source: 数据源类型
            
        Returns:
            任务ID
            
        Raises:
            ValueError: 参数无效时抛出
        """
        # 验证参数
        if not session_ids:
            raise ValueError("会话ID列表不能为空")
        
        if format_type not in ['html', 'json', 'markdown']:
            raise ValueError(f"不支持的格式类型: {format_type}")
        
        if source not in ['cursor', 'augment', 'cursor-augment', 'idea-augment', 'pycharm-augment']:
            raise ValueError(f"不支持的数据源: {source}")
        
        # 检查并发任务数限制
        with self.task_lock:
            active_count = len([task for task in self.tasks.values() 
                              if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]])
            if active_count >= self.max_concurrent_tasks:
                raise ValueError(f"并发任务数已达上限 ({self.max_concurrent_tasks})")
        
        # 创建任务
        task_id = str(uuid.uuid4())
        task_info = BatchTaskInfo(
            task_id=task_id,
            session_ids=session_ids.copy(),
            format_type=format_type,
            source=source,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        
        with self.task_lock:
            self.tasks[task_id] = task_info
        
        self.logger.info(f"创建批量下载任务 {task_id}: {len(session_ids)} 个会话, 格式: {format_type}, 数据源: {source}")
        
        # 启动任务处理线程
        task_thread = threading.Thread(target=self._process_batch_task, args=(task_id,))
        task_thread.start()
        self.active_tasks[task_id] = task_thread
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息字典，如果任务不存在则返回None
        """
        with self.task_lock:
            task_info = self.tasks.get(task_id)
            if not task_info:
                return None
            
            # 转换为字典并处理datetime序列化
            status_dict = asdict(task_info)
            status_dict['created_at'] = task_info.created_at.isoformat()
            status_dict['started_at'] = task_info.started_at.isoformat() if task_info.started_at else None
            status_dict['completed_at'] = task_info.completed_at.isoformat() if task_info.completed_at else None
            status_dict['status'] = task_info.status.value
            
            return status_dict
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        with self.task_lock:
            task_info = self.tasks.get(task_id)
            if not task_info:
                return False
            
            if task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False
            
            # 标记为取消状态
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            
            self.logger.info(f"任务 {task_id} 已被取消")
            
            # 清理输出文件
            if task_info.output_file_path and os.path.exists(task_info.output_file_path):
                try:
                    os.remove(task_info.output_file_path)
                except Exception as e:
                    self.logger.warning(f"清理取消任务的输出文件失败: {e}")
            
            return True
    
    def get_task_file_path(self, task_id: str) -> Optional[str]:
        """
        获取任务的输出文件路径
        
        Args:
            task_id: 任务ID
            
        Returns:
            文件路径，如果任务未完成或不存在则返回None
        """
        with self.task_lock:
            task_info = self.tasks.get(task_id)
            if not task_info or task_info.status != TaskStatus.COMPLETED:
                return None
            
            return task_info.output_file_path
    
    def _process_batch_task(self, task_id: str):
        """
        处理批量下载任务的主要逻辑
        
        Args:
            task_id: 任务ID
        """
        try:
            with self.task_lock:
                task_info = self.tasks[task_id]
                task_info.status = TaskStatus.PROCESSING
                task_info.started_at = datetime.now()
            
            self.logger.info(f"开始处理批量下载任务 {task_id}")
            
            # 动态导入避免循环导入
            import server

            # 获取所有聊天数据
            all_chats = server.extract_chats(source=task_info.source)
            chat_dict = {chat['session']['composerId']: chat for chat in all_chats
                        if 'session' in chat and chat['session'] and 'composerId' in chat['session']}
            
            # 验证会话ID是否存在
            valid_session_ids = []
            for session_id in task_info.session_ids:
                if session_id in chat_dict:
                    valid_session_ids.append(session_id)
                else:
                    task_info.failed_sessions.append(session_id)
                    self.logger.warning(f"会话 {session_id} 不存在")
            
            if not valid_session_ids:
                raise ValueError("没有找到有效的会话")
            
            # 并行处理各个会话
            exported_files = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_session = {
                    executor.submit(self._export_single_chat, chat_dict[session_id], task_info.format_type): session_id
                    for session_id in valid_session_ids
                }
                
                # 处理完成的任务
                for future in as_completed(future_to_session):
                    session_id = future_to_session[future]
                    
                    # 检查是否被取消
                    with self.task_lock:
                        if task_info.status == TaskStatus.CANCELLED:
                            self.logger.info(f"任务 {task_id} 已被取消，停止处理")
                            return
                    
                    try:
                        file_path, filename = future.result()
                        exported_files.append((file_path, filename))
                        
                        # 更新进度
                        with self.task_lock:
                            task_info.completed_count += 1
                            task_info.progress = task_info.completed_count / len(valid_session_ids)
                        
                        self.logger.debug(f"会话 {session_id} 导出完成")
                        
                    except Exception as e:
                        self.logger.error(f"导出会话 {session_id} 失败: {e}")
                        with self.task_lock:
                            task_info.failed_sessions.append(session_id)
            
            # 检查是否有成功导出的文件
            if not exported_files:
                raise ValueError("没有成功导出任何文件")
            
            # 打包文件
            from file_packager import FilePackager
            packager = FilePackager()
            
            output_filename = f"batch_export_{task_id[:8]}_{task_info.format_type}.zip"
            output_path = self.temp_dir / output_filename
            
            packager.create_zip_package(exported_files, str(output_path))
            
            # 清理临时文件
            for file_path, _ in exported_files:
                try:
                    os.remove(file_path)
                except Exception as e:
                    self.logger.warning(f"清理临时文件失败: {e}")
            
            # 更新任务状态
            with self.task_lock:
                task_info.status = TaskStatus.COMPLETED
                task_info.completed_at = datetime.now()
                task_info.output_file_path = str(output_path)
                task_info.progress = 1.0
            
            self.logger.info(f"批量下载任务 {task_id} 完成，输出文件: {output_path}")
            
        except Exception as e:
            self.logger.error(f"处理批量下载任务 {task_id} 失败: {e}")
            with self.task_lock:
                task_info = self.tasks[task_id]
                task_info.status = TaskStatus.FAILED
                task_info.completed_at = datetime.now()
                task_info.error_message = str(e)
        
        finally:
            # 清理活动任务记录
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    def _export_single_chat(self, chat_data: Dict[str, Any], format_type: str) -> Tuple[str, str]:
        """
        导出单个聊天记录
        
        Args:
            chat_data: 聊天数据
            format_type: 导出格式
            
        Returns:
            (文件路径, 文件名) 元组
        """
        # 动态导入避免循环导入
        import server

        # 格式化聊天数据
        formatted_chat = server.format_chat_for_frontend(chat_data)
        session_id = formatted_chat.get('session', {}).get('composerId', 'unknown')

        # 生成文件内容
        if format_type == 'json':
            content = json.dumps(formatted_chat, indent=2, ensure_ascii=False)
            extension = 'json'
            mimetype = 'application/json'
        elif format_type == 'markdown':
            content = server.generate_standalone_markdown(formatted_chat)
            extension = 'md'
            mimetype = 'text/markdown'
        else:  # html
            content = server.generate_standalone_html(formatted_chat)
            extension = 'html'
            mimetype = 'text/html'
        
        # 保存到临时文件
        filename = f"chat_{session_id[:8]}.{extension}"
        temp_file_path = self.temp_dir / f"{uuid.uuid4()}_{filename}"
        
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(temp_file_path), filename
    
    def _cleanup_old_tasks(self):
        """清理旧任务的后台线程"""
        while True:
            try:
                time.sleep(3600)  # 每小时检查一次
                
                cutoff_time = datetime.now() - timedelta(hours=24)  # 24小时前
                
                with self.task_lock:
                    tasks_to_remove = []
                    for task_id, task_info in self.tasks.items():
                        if (task_info.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] 
                            and task_info.completed_at and task_info.completed_at < cutoff_time):
                            
                            # 清理输出文件
                            if task_info.output_file_path and os.path.exists(task_info.output_file_path):
                                try:
                                    os.remove(task_info.output_file_path)
                                except Exception as e:
                                    self.logger.warning(f"清理旧任务文件失败: {e}")
                            
                            tasks_to_remove.append(task_id)
                    
                    # 移除旧任务
                    for task_id in tasks_to_remove:
                        del self.tasks[task_id]
                        self.logger.info(f"清理旧任务: {task_id}")
                        
            except Exception as e:
                self.logger.error(f"清理旧任务时出错: {e}")


# 全局批量下载管理器实例
batch_download_manager = BatchDownloadManager()
