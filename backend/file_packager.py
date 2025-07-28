#!/usr/bin/env python3
"""
文件打包器
负责将多个导出的聊天文件打包为ZIP压缩包
支持流式打包以避免内存溢出
"""

import os
import zipfile
import logging
from typing import List, Tuple, Optional
from pathlib import Path
import tempfile
from datetime import datetime


class FilePackager:
    """文件打包器类"""
    
    def __init__(self):
        """初始化文件打包器"""
        self.logger = logging.getLogger(__name__)
    
    def create_zip_package(self, 
                          file_list: List[Tuple[str, str]], 
                          output_path: str,
                          compression_level: int = 6) -> bool:
        """
        创建ZIP压缩包
        
        Args:
            file_list: 文件列表，每个元素为 (文件路径, 压缩包内文件名) 元组
            output_path: 输出ZIP文件路径
            compression_level: 压缩级别 (0-9, 0为不压缩, 9为最高压缩)
            
        Returns:
            是否成功创建压缩包
        """
        try:
            self.logger.info(f"开始创建ZIP压缩包: {output_path}")
            self.logger.info(f"包含 {len(file_list)} 个文件")
            
            # 确保输出目录存在
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建ZIP文件
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
                
                # 添加元数据文件
                self._add_metadata_file(zipf, len(file_list))
                
                # 添加所有文件
                for file_path, archive_name in file_list:
                    if not os.path.exists(file_path):
                        self.logger.warning(f"文件不存在，跳过: {file_path}")
                        continue
                    
                    try:
                        # 使用流式方式添加文件以节省内存
                        self._add_file_to_zip(zipf, file_path, archive_name)
                        self.logger.debug(f"已添加文件到压缩包: {archive_name}")
                        
                    except Exception as e:
                        self.logger.error(f"添加文件到压缩包失败 {file_path}: {e}")
                        continue
            
            # 验证生成的ZIP文件
            if self._validate_zip_file(output_path):
                file_size = os.path.getsize(output_path)
                self.logger.info(f"ZIP压缩包创建成功: {output_path} (大小: {self._format_file_size(file_size)})")
                return True
            else:
                self.logger.error("ZIP文件验证失败")
                return False
                
        except Exception as e:
            self.logger.error(f"创建ZIP压缩包失败: {e}")
            return False
    
    def _add_file_to_zip(self, zipf: zipfile.ZipFile, file_path: str, archive_name: str):
        """
        将文件添加到ZIP压缩包中
        
        Args:
            zipf: ZipFile对象
            file_path: 源文件路径
            archive_name: 压缩包内的文件名
        """
        # 确保压缩包内的文件名是安全的
        safe_archive_name = self._sanitize_filename(archive_name)
        
        # 检查文件大小，对于大文件使用流式处理
        file_size = os.path.getsize(file_path)
        
        if file_size > 50 * 1024 * 1024:  # 50MB以上的文件使用流式处理
            self._add_large_file_to_zip(zipf, file_path, safe_archive_name)
        else:
            # 小文件直接添加
            zipf.write(file_path, safe_archive_name)
    
    def _add_large_file_to_zip(self, zipf: zipfile.ZipFile, file_path: str, archive_name: str):
        """
        流式添加大文件到ZIP压缩包
        
        Args:
            zipf: ZipFile对象
            file_path: 源文件路径
            archive_name: 压缩包内的文件名
        """
        with open(file_path, 'rb') as src_file:
            with zipf.open(archive_name, 'w') as dest_file:
                # 分块读取和写入，避免内存溢出
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = src_file.read(chunk_size)
                    if not chunk:
                        break
                    dest_file.write(chunk)
    
    def _add_metadata_file(self, zipf: zipfile.ZipFile, file_count: int):
        """
        添加元数据文件到压缩包
        
        Args:
            zipf: ZipFile对象
            file_count: 文件数量
        """
        metadata = {
            "export_info": {
                "tool_name": "AI IDE Chat Export Tool",
                "export_time": datetime.now().isoformat(),
                "file_count": file_count,
                "format_version": "1.0"
            },
            "instructions": {
                "description": "This archive contains exported AI IDE chat conversations",
                "file_naming": "Files are named as chat_[session_id].[format]",
                "supported_formats": ["html", "json", "markdown"]
            }
        }
        
        import json
        metadata_content = json.dumps(metadata, indent=2, ensure_ascii=False)
        
        # 添加元数据文件
        zipf.writestr("README.json", metadata_content)
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，确保在ZIP压缩包中是安全的
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的安全文件名
        """
        # 移除或替换不安全的字符
        unsafe_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        safe_filename = filename
        
        for char in unsafe_chars:
            safe_filename = safe_filename.replace(char, '_')
        
        # 确保文件名不为空且不以点开头
        if not safe_filename or safe_filename.startswith('.'):
            safe_filename = f"file_{safe_filename}"
        
        # 限制文件名长度
        if len(safe_filename) > 255:
            name, ext = os.path.splitext(safe_filename)
            max_name_length = 255 - len(ext)
            safe_filename = name[:max_name_length] + ext
        
        return safe_filename
    
    def _validate_zip_file(self, zip_path: str) -> bool:
        """
        验证ZIP文件的完整性
        
        Args:
            zip_path: ZIP文件路径
            
        Returns:
            文件是否有效
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # 测试ZIP文件的完整性
                bad_file = zipf.testzip()
                if bad_file:
                    self.logger.error(f"ZIP文件中损坏的文件: {bad_file}")
                    return False
                
                # 检查是否包含文件
                file_list = zipf.namelist()
                if not file_list:
                    self.logger.error("ZIP文件为空")
                    return False
                
                self.logger.debug(f"ZIP文件验证通过，包含 {len(file_list)} 个文件")
                return True
                
        except zipfile.BadZipFile:
            self.logger.error("无效的ZIP文件格式")
            return False
        except Exception as e:
            self.logger.error(f"验证ZIP文件时出错: {e}")
            return False
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        格式化文件大小显示
        
        Args:
            size_bytes: 文件大小（字节）
            
        Returns:
            格式化的文件大小字符串
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def extract_zip_info(self, zip_path: str) -> Optional[dict]:
        """
        提取ZIP文件信息
        
        Args:
            zip_path: ZIP文件路径
            
        Returns:
            ZIP文件信息字典，失败时返回None
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                file_list = zipf.namelist()
                total_size = sum(zipf.getinfo(name).file_size for name in file_list)
                compressed_size = sum(zipf.getinfo(name).compress_size for name in file_list)
                
                info = {
                    "file_count": len(file_list),
                    "total_size": total_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": round((1 - compressed_size / total_size) * 100, 2) if total_size > 0 else 0,
                    "files": file_list
                }
                
                return info
                
        except Exception as e:
            self.logger.error(f"提取ZIP文件信息失败: {e}")
            return None
    
    def create_directory_structure(self, file_list: List[Tuple[str, str]], base_dir: str = "chats") -> List[Tuple[str, str]]:
        """
        为文件列表创建目录结构
        
        Args:
            file_list: 原始文件列表
            base_dir: 基础目录名
            
        Returns:
            带有目录结构的文件列表
        """
        structured_list = []
        
        for file_path, filename in file_list:
            # 根据文件类型创建子目录
            _, ext = os.path.splitext(filename)
            ext = ext.lower().lstrip('.')
            
            if ext in ['html', 'htm']:
                subdir = "html"
            elif ext == 'json':
                subdir = "json"
            elif ext in ['md', 'markdown']:
                subdir = "markdown"
            else:
                subdir = "other"
            
            # 构建压缩包内的路径
            archive_path = f"{base_dir}/{subdir}/{filename}"
            structured_list.append((file_path, archive_path))
        
        return structured_list
    
    def get_temp_dir(self) -> str:
        """
        获取临时目录路径
        
        Returns:
            临时目录路径
        """
        temp_dir = Path(tempfile.gettempdir()) / "ai_ide_file_packager"
        temp_dir.mkdir(exist_ok=True)
        return str(temp_dir)
    
    def cleanup_temp_files(self, file_paths: List[str]):
        """
        清理临时文件
        
        Args:
            file_paths: 要清理的文件路径列表
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.debug(f"已清理临时文件: {file_path}")
            except Exception as e:
                self.logger.warning(f"清理临时文件失败 {file_path}: {e}")
