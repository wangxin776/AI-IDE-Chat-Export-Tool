#!/usr/bin/env python3
"""
Simple API server to serve Cursor chat data for the web interface.
"""

import json
import uuid
import logging
import datetime
import os
import platform
import sqlite3
import argparse
import pathlib
from collections import defaultdict
from typing import Dict, Any, Iterable, Optional
from pathlib import Path
from flask import Flask, Response, jsonify, send_from_directory, request
from flask_cors import CORS

# Import Augment data extractor
from augment_extractor import AugmentDataExtractor

# Import configuration management
from config_manager import ConfigManager
from path_validator import PathValidator

# Import batch download manager
from batch_download_manager import batch_download_manager

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='../frontend/build')
CORS(app)

# Initialize configuration manager and path validator
config_manager = ConfigManager()
path_validator = PathValidator()

################################################################################
# Cursor storage roots
################################################################################
def cursor_root() -> pathlib.Path:
    h = pathlib.Path.home()
    s = platform.system()
    if s == "Darwin":   return h / "Library" / "Application Support" / "Cursor"
    if s == "Windows":  return h / "AppData" / "Roaming" / "Cursor"
    if s == "Linux":    return h / ".config" / "Cursor"
    raise RuntimeError(f"Unsupported OS: {s}")

################################################################################
# Helpers
################################################################################
def j(cur: sqlite3.Cursor, table: str, key: str):
    cur.execute(f"SELECT value FROM {table} WHERE key=?", (key,))
    row = cur.fetchone()
    if row:
        try:    return json.loads(row[0])
        except Exception as e: 
            logger.debug(f"Failed to parse JSON for {key}: {e}")
    return None

def iter_bubbles_from_disk_kv(db: pathlib.Path) -> Iterable[tuple[str,str,str,str]]:
    """Yield (composerId, role, text, db_path) from cursorDiskKV table."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
        if not cur.fetchone():
            con.close()
            return
        
        cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'")
    except sqlite3.DatabaseError as e:
        logger.debug(f"Database error with {db}: {e}")
        return
    
    db_path_str = str(db)
    
    for k, v in cur.fetchall():
        try:
            if v is None:
                continue
                
            b = json.loads(v)
        except Exception as e:
            logger.debug(f"Failed to parse bubble JSON for key {k}: {e}")
            continue
        
        txt = (b.get("text") or b.get("richText") or "").strip()
        if not txt:         continue
        role = "user" if b.get("type") == 1 else "assistant"
        composerId = k.split(":")[1]  # Format is bubbleId:composerId:bubbleId
        yield composerId, role, txt, db_path_str
    
    con.close()

def iter_chat_from_item_table(db: pathlib.Path) -> Iterable[tuple[str,str,str,str]]:
    """Yield (composerId, role, text, db_path) from ItemTable."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        
        # Try to get chat data from workbench.panel.aichat.view.aichat.chatdata
        chat_data = j(cur, "ItemTable", "workbench.panel.aichat.view.aichat.chatdata")
        if chat_data and "tabs" in chat_data:
            for tab in chat_data.get("tabs", []):
                tab_id = tab.get("tabId", "unknown")
                for bubble in tab.get("bubbles", []):
                    bubble_type = bubble.get("type")
                    if not bubble_type:
                        continue
                    
                    # Extract text from various possible fields
                    text = ""
                    if "text" in bubble:
                        text = bubble["text"]
                    elif "content" in bubble:
                        text = bubble["content"]
                    
                    if text and isinstance(text, str):
                        role = "user" if bubble_type == "user" else "assistant"
                        yield tab_id, role, text, str(db)
        
        # Check for composer data
        composer_data = j(cur, "ItemTable", "composer.composerData")
        if composer_data:
            for comp in composer_data.get("allComposers", []):
                comp_id = comp.get("composerId", "unknown")
                messages = comp.get("messages", [])
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if content:
                        yield comp_id, role, content, str(db)
        
        # Also check for aiService entries
        for key_prefix in ["aiService.prompts", "aiService.generations"]:
            try:
                cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE ?", (f"{key_prefix}%",))
                for k, v in cur.fetchall():
                    try:
                        data = json.loads(v)
                        if isinstance(data, list):
                            for item in data:
                                if "id" in item and "text" in item:
                                    role = "user" if "prompts" in key_prefix else "assistant"
                                    yield item.get("id", "unknown"), role, item.get("text", ""), str(db)
                    except json.JSONDecodeError:
                        continue
            except sqlite3.Error:
                continue
    
    except sqlite3.DatabaseError as e:
        logger.debug(f"Database error in ItemTable with {db}: {e}")
        return
    finally:
        if 'con' in locals():
            con.close()

def iter_composer_data(db: pathlib.Path) -> Iterable[tuple[str,dict,str]]:
    """Yield (composerId, composerData, db_path) from cursorDiskKV table."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()
        # Check if table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cursorDiskKV'")
        if not cur.fetchone():
            con.close()
            return
        
        cur.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'")
    except sqlite3.DatabaseError as e:
        logger.debug(f"Database error with {db}: {e}")
        return
    
    db_path_str = str(db)
    
    for k, v in cur.fetchall():
        try:
            if v is None:
                continue
                
            composer_data = json.loads(v)
            composer_id = k.split(":")[1]
            yield composer_id, composer_data, db_path_str
            
        except Exception as e:
            logger.debug(f"Failed to parse composer data for key {k}: {e}")
            continue
    
    con.close()

################################################################################
# Workspace discovery
################################################################################
def workspaces(base: pathlib.Path):
    ws_root = base / "User" / "workspaceStorage"
    if not ws_root.exists():
        return
    for folder in ws_root.iterdir():
        db = folder / "state.vscdb"
        if db.exists():
            yield folder.name, db

def extract_project_name_from_path(root_path, debug=False):
    """
    Extract a project name from a path, skipping user directories.
    """
    if not root_path or root_path == '/':
        return "Root"
        
    path_parts = [p for p in root_path.split('/') if p]
    
    # Skip common user directory patterns
    project_name = None
    home_dir_patterns = ['Users', 'home']
    
    # Get current username for comparison
    current_username = os.path.basename(os.path.expanduser('~'))
    
    # Find user directory in path
    username_index = -1
    for i, part in enumerate(path_parts):
        if part in home_dir_patterns:
            username_index = i + 1
            break
    
    # If this is just /Users/username with no deeper path, don't use username as project
    if username_index >= 0 and username_index < len(path_parts) and path_parts[username_index] == current_username:
        if len(path_parts) <= username_index + 1:
            return "Home Directory"
    
    if username_index >= 0 and username_index + 1 < len(path_parts):
        # First try specific project directories we know about by name
        known_projects = ['genaisf', 'cursor-view', 'cursor', 'cursor-apps', 'universal-github', 'inquiry']
        
        # Look at the most specific/deepest part of the path first
        for i in range(len(path_parts)-1, username_index, -1):
            if path_parts[i] in known_projects:
                project_name = path_parts[i]
                if debug:
                    logger.debug(f"Found known project name from specific list: {project_name}")
                break
        
        # If no known project found, use the last part of the path as it's likely the project directory
        if not project_name and len(path_parts) > username_index + 1:
            # Check if we have a structure like /Users/username/Documents/codebase/project_name
            if 'Documents' in path_parts and 'codebase' in path_parts:
                doc_index = path_parts.index('Documents')
                codebase_index = path_parts.index('codebase')
                
                # If there's a path component after 'codebase', use that as the project name
                if codebase_index + 1 < len(path_parts):
                    project_name = path_parts[codebase_index + 1]
                    if debug:
                        logger.debug(f"Found project name in Documents/codebase structure: {project_name}")
            
            # If no specific structure found, use the last component of the path
            if not project_name:
                project_name = path_parts[-1]
                if debug:
                    logger.debug(f"Using last path component as project name: {project_name}")
        
        # Skip username as project name
        if project_name == current_username:
            project_name = 'Home Directory'
            if debug:
                logger.debug(f"Avoided using username as project name")
        
        # Skip common project container directories
        project_containers = ['Documents', 'Projects', 'Code', 'workspace', 'repos', 'git', 'src', 'codebase']
        if project_name in project_containers:
            # Don't use container directories as project names
            # Try to use the next component if available
            container_index = path_parts.index(project_name)
            if container_index + 1 < len(path_parts):
                project_name = path_parts[container_index + 1]
                if debug:
                    logger.debug(f"Skipped container dir, using next component as project name: {project_name}")
        
        # If we still don't have a project name, use the first non-system directory after username
        if not project_name and username_index + 1 < len(path_parts):
            system_dirs = ['Library', 'Applications', 'System', 'var', 'opt', 'tmp']
            for i in range(username_index + 1, len(path_parts)):
                if path_parts[i] not in system_dirs and path_parts[i] not in project_containers:
                    project_name = path_parts[i]
                    if debug:
                        logger.debug(f"Using non-system dir as project name: {project_name}")
                    break
    else:
        # If not in a user directory, use the basename
        project_name = path_parts[-1] if path_parts else "Root"
        if debug:
            logger.debug(f"Using basename as project name: {project_name}")
    
    # Final check: don't return username as project name
    if project_name == current_username:
        project_name = "Home Directory"
        if debug:
            logger.debug(f"Final check: replaced username with 'Home Directory'")
    
    return project_name if project_name else "Unknown Project"

def workspace_info(db: pathlib.Path):
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = con.cursor()

        # Get file paths from history entries to extract the project name
        proj = {"name": "(unknown)", "rootPath": "(unknown)"}
        ents = j(cur,"ItemTable","history.entries") or []
        
        # Extract file paths from history entries, stripping the file:/// scheme
        paths = []
        for e in ents:
            resource = e.get("editor", {}).get("resource", "")
            if resource and resource.startswith("file:///"):
                paths.append(resource[len("file:///"):])
        
        # If we found file paths, extract the project name using the longest common prefix
        if paths:
            logger.debug(f"Found {len(paths)} paths in history entries")
            
            # Get the longest common prefix
            common_prefix = os.path.commonprefix(paths)
            logger.debug(f"Common prefix: {common_prefix}")
            
            # Find the last directory separator in the common prefix
            last_separator_index = common_prefix.rfind('/')
            if last_separator_index > 0:
                project_root = common_prefix[:last_separator_index]
                logger.debug(f"Project root from common prefix: {project_root}")
                
                # Extract the project name using the helper function
                project_name = extract_project_name_from_path(project_root, debug=True)
                
                proj = {"name": project_name, "rootPath": "/" + project_root.lstrip('/')}
        
        # Try backup methods if we didn't get a project name
        if proj["name"] == "(unknown)":
            logger.debug("Trying backup methods for project name")
            
            # Check debug.selectedroot as a fallback
            selected_root = j(cur, "ItemTable", "debug.selectedroot")
            if selected_root and isinstance(selected_root, str) and selected_root.startswith("file:///"):
                path = selected_root[len("file:///"):]
                if path:
                    root_path = "/" + path.strip("/")
                    logger.debug(f"Project root from debug.selectedroot: {root_path}")
                    
                    # Extract the project name using the helper function
                    project_name = extract_project_name_from_path(root_path, debug=True)
                    
                    if project_name:
                        proj = {"name": project_name, "rootPath": root_path}

        # composers meta
        comp_meta={}
        cd = j(cur,"ItemTable","composer.composerData") or {}
        for c in cd.get("allComposers",[]):
            comp_meta[c["composerId"]] = {
                "title": c.get("name","(untitled)"),
                "createdAt": c.get("createdAt"),
                "lastUpdatedAt": c.get("lastUpdatedAt")
            }
        
        # Try to get composer info from workbench.panel.aichat.view.aichat.chatdata
        chat_data = j(cur, "ItemTable", "workbench.panel.aichat.view.aichat.chatdata") or {}
        for tab in chat_data.get("tabs", []):
            tab_id = tab.get("tabId")
            if tab_id and tab_id not in comp_meta:
                comp_meta[tab_id] = {
                    "title": f"Chat {tab_id[:8]}",
                    "createdAt": None,
                    "lastUpdatedAt": None
                }
    except sqlite3.DatabaseError as e:
        logger.debug(f"Error getting workspace info from {db}: {e}")
        proj = {"name": "(unknown)", "rootPath": "(unknown)"}
        comp_meta = {}
    finally:
        if 'con' in locals():
            con.close()
            
    return proj, comp_meta

################################################################################
# GlobalStorage
################################################################################
def global_storage_path(base: pathlib.Path) -> pathlib.Path:
    """Return path to the global storage state.vscdb."""
    global_db = base / "User" / "globalStorage" / "state.vscdb"
    if global_db.exists():
        return global_db
    
    # Legacy paths
    g_dirs = [base/"User"/"globalStorage"/"cursor.cursor",
              base/"User"/"globalStorage"/"cursor"]
    for d in g_dirs:
        if d.exists():
            for file in d.glob("*.sqlite"):
                return file
    
    return None

################################################################################
# Augment data extraction
################################################################################
def extract_augment_chats(custom_path: Optional[str] = None) -> list[Dict[str,Any]]:
    """
    提取Augment对话数据并转换为cursor-view兼容格式

    Args:
        custom_path: 自定义路径，如果为None则使用默认路径

    Returns:
        cursor-view格式的Augment对话列表
    """
    try:
        logger.info("开始提取Augment对话数据...")

        # 创建Augment数据提取器，传入自定义路径
        extractor = AugmentDataExtractor(custom_path)

        # 提取Augment对话
        conversations = extractor.extract_augment_conversations()

        if not conversations:
            logger.warning("未找到Augment对话数据")
            return []

        # 转换为cursor-view兼容格式
        cursor_format_chats = extractor.convert_to_cursor_format(conversations)

        logger.info(f"成功提取并转换 {len(cursor_format_chats)} 个Augment对话")
        return cursor_format_chats

    except Exception as e:
        logger.error(f"提取Augment对话失败: {e}")
        return []

def extract_cursor_augment_chats(custom_path: Optional[str] = None) -> list[Dict[str,Any]]:
    """
    提取Cursor中的Augment对话数据并转换为cursor-view兼容格式

    Args:
        custom_path: 自定义路径，如果为None则使用默认路径

    Returns:
        cursor-view格式的Cursor Augment对话列表
    """
    try:
        logger.info("开始提取Cursor Augment对话数据...")

        # 创建Cursor Augment数据提取器，传入自定义路径
        from cursor_augment_extractor import CursorAugmentExtractor
        extractor = CursorAugmentExtractor(custom_path)

        # 提取Cursor Augment对话
        conversations = extractor.extract_augment_conversations()

        if not conversations:
            logger.warning("未找到Cursor Augment对话数据")
            return []

        # 转换为cursor-view兼容格式
        cursor_format_chats = extractor.convert_to_cursor_view_format(conversations)

        logger.info(f"成功提取并转换 {len(cursor_format_chats)} 个Cursor Augment对话")
        return cursor_format_chats

    except Exception as e:
        logger.error(f"提取Cursor Augment对话失败: {e}")
        return []

def extract_idea_augment_chats(custom_path: Optional[str] = None) -> list[Dict[str,Any]]:
    """
    提取IDEA中的Augment对话数据并转换为cursor-view兼容格式

    Args:
        custom_path: 自定义路径，如果为None则使用默认路径

    Returns:
        cursor-view格式的IDEA Augment对话列表
    """
    try:
        logger.info("开始提取IDEA Augment对话数据...")

        # 创建IDEA Augment数据提取器，传入自定义路径
        from idea_augment_extractor import IdeaAugmentExtractor
        extractor = IdeaAugmentExtractor(custom_path)

        # 提取IDEA Augment对话
        conversations = extractor.extract_augment_conversations()

        if not conversations:
            logger.warning("未找到IDEA Augment对话数据")
            return []

        # 转换为cursor-view兼容格式
        cursor_format_chats = extractor.convert_to_cursor_view_format(conversations)

        logger.info(f"成功提取并转换 {len(cursor_format_chats)} 个IDEA Augment对话")
        return cursor_format_chats

    except Exception as e:
        logger.error(f"提取IDEA Augment对话失败: {e}")
        return []

def extract_pycharm_augment_chats(custom_path: Optional[str] = None) -> list[Dict[str,Any]]:
    """
    提取PyCharm中的Augment对话数据并转换为cursor-view兼容格式

    Args:
        custom_path: 自定义路径，如果为None则使用默认路径

    Returns:
        cursor-view格式的PyCharm Augment对话列表
    """
    try:
        logger.info("开始提取PyCharm Augment对话数据...")

        # 创建PyCharm Augment数据提取器，传入自定义路径
        from pycharm_augment_extractor import PyCharmAugmentExtractor
        extractor = PyCharmAugmentExtractor(custom_path)

        # 提取PyCharm Augment对话
        conversations = extractor.extract_augment_conversations()

        if not conversations:
            logger.warning("未找到PyCharm Augment对话数据")
            return []

        # 转换为cursor-view兼容格式
        cursor_format_chats = extractor.convert_to_cursor_view_format(conversations)

        logger.info(f"成功提取并转换 {len(cursor_format_chats)} 个PyCharm Augment对话")
        return cursor_format_chats

    except Exception as e:
        logger.error(f"提取PyCharm Augment对话失败: {e}")
        return []

def extract_warp_chats(custom_path: Optional[str] = None) -> list[Dict[str,Any]]:
    """
    提取Warp Terminal中的AI对话数据并转换为cursor-view兼容格式

    Args:
        custom_path: 自定义路径，如果为None则使用默认路径

    Returns:
        cursor-view格式的Warp对话列表
    """
    try:
        logger.info("开始提取Warp AI对话数据...")

        # 创建Warp数据提取器，传入自定义路径
        from warp_extractor import WarpDataExtractor
        extractor = WarpDataExtractor(custom_path)

        # 提取Warp对话
        conversations = extractor.extract_warp_conversations()

        if not conversations:
            logger.warning("未找到Warp对话数据")
            return []

        # 转换为cursor-view兼容格式
        cursor_format_chats = extractor.convert_to_cursor_view_format(conversations)

        logger.info(f"成功提取并转换 {len(cursor_format_chats)} 个Warp对话")
        return cursor_format_chats

    except Exception as e:
        logger.error(f"提取Warp对话失败: {e}")
        return []

################################################################################
# Extraction pipeline
################################################################################
def extract_chats(source: str = 'cursor') -> list[Dict[str,Any]]:
    """
    提取对话数据，支持多种数据源

    Args:
        source: 数据源类型 ('cursor', 'augment', 或 'cursor-augment')

    Returns:
        对话数据列表
    """
    logger.info(f"提取对话数据，数据源: {source}")

    # 获取自定义路径配置
    custom_path = config_manager.get_path(source)

    # 如果是VSCode Augment数据源，使用Augment提取器
    if source == 'augment':
        return extract_augment_chats(custom_path)

    # 如果是Cursor Augment数据源，使用Cursor Augment提取器
    elif source == 'cursor-augment':
        return extract_cursor_augment_chats(custom_path)

    # 如果是IDEA Augment数据源，使用IDEA Augment提取器
    elif source == 'idea-augment':
        return extract_idea_augment_chats(custom_path)

    # 如果是PyCharm Augment数据源，使用PyCharm Augment提取器
    elif source == 'pycharm-augment':
        return extract_pycharm_augment_chats(custom_path)
    
    # 如果是Warp数据源，使用Warp提取器
    elif source == 'warp':
        return extract_warp_chats(custom_path)

    # 默认使用Cursor数据源
    if custom_path:
        # 如果有自定义Cursor路径，使用它
        root = pathlib.Path(custom_path)
        if not root.exists():
            logger.warning(f"自定义Cursor路径不存在: {custom_path}，回退到默认路径")
            root = cursor_root()
        else:
            logger.info(f"使用自定义Cursor路径: {custom_path}")
    else:
        root = cursor_root()
    logger.debug(f"Using Cursor root: {root}")

    # Diagnostic: Check for AI-related keys in the first workspace
    if os.environ.get("CURSOR_CHAT_DIAGNOSTICS"):
        try:
            first_ws = next(workspaces(root))
            if first_ws:
                ws_id, db = first_ws
                logger.debug(f"\n--- DIAGNOSTICS for workspace {ws_id} ---")
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                cur = con.cursor()
                
                # List all tables
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                logger.debug(f"Tables in workspace DB: {tables}")
                
                # Search for AI-related keys
                if "ItemTable" in tables:
                    for pattern in ['%ai%', '%chat%', '%composer%', '%prompt%', '%generation%']:
                        cur.execute("SELECT key FROM ItemTable WHERE key LIKE ?", (pattern,))
                        keys = [row[0] for row in cur.fetchall()]
                        if keys:
                            logger.debug(f"Keys matching '{pattern}': {keys}")
                
                con.close()
                
            # Check global storage
            global_db = global_storage_path(root)
            if global_db:
                logger.debug(f"\n--- DIAGNOSTICS for global storage ---")
                con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
                cur = con.cursor()
                
                # List all tables
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cur.fetchall()]
                logger.debug(f"Tables in global DB: {tables}")
                
                # Search for AI-related keys in ItemTable
                if "ItemTable" in tables:
                    for pattern in ['%ai%', '%chat%', '%composer%', '%prompt%', '%generation%']:
                        cur.execute("SELECT key FROM ItemTable WHERE key LIKE ?", (pattern,))
                        keys = [row[0] for row in cur.fetchall()]
                        if keys:
                            logger.debug(f"Keys matching '{pattern}': {keys}")
                
                # Check for keys in cursorDiskKV
                if "cursorDiskKV" in tables:
                    cur.execute("SELECT DISTINCT substr(key, 1, instr(key, ':') - 1) FROM cursorDiskKV")
                    prefixes = [row[0] for row in cur.fetchall()]
                    logger.debug(f"Key prefixes in cursorDiskKV: {prefixes}")
                
                con.close()
            
            logger.debug("\n--- END DIAGNOSTICS ---\n")
        except Exception as e:
            logger.debug(f"Error in diagnostics: {e}")

    # map lookups
    ws_proj  : Dict[str,Dict[str,Any]] = {}
    comp_meta: Dict[str,Dict[str,Any]] = {}
    comp2ws  : Dict[str,str]           = {}
    sessions : Dict[str,Dict[str,Any]] = defaultdict(lambda: {"messages":[]})

    # 1. Process workspace DBs first
    logger.debug("Processing workspace databases...")
    ws_count = 0
    for ws_id, db in workspaces(root):
        ws_count += 1
        logger.debug(f"Processing workspace {ws_id} - {db}")
        proj, meta = workspace_info(db)
        ws_proj[ws_id] = proj
        for cid, m in meta.items():
            comp_meta[cid] = m
            comp2ws[cid] = ws_id
        
        # Extract chat data from workspace's state.vscdb
        msg_count = 0
        for cid, role, text, db_path in iter_chat_from_item_table(db):
            # Add the message
            sessions[cid]["messages"].append({"role": role, "content": text})
            # Make sure to record the database path
            if "db_path" not in sessions[cid]:
                sessions[cid]["db_path"] = db_path
            msg_count += 1
            if cid not in comp_meta:
                comp_meta[cid] = {"title": f"Chat {cid[:8]}", "createdAt": None, "lastUpdatedAt": None}
                comp2ws[cid] = ws_id
        logger.debug(f"  - Extracted {msg_count} messages from workspace {ws_id}")
    
    logger.debug(f"Processed {ws_count} workspaces")

    # 2. Process global storage
    global_db = global_storage_path(root)
    if global_db:
        logger.debug(f"Processing global storage: {global_db}")
        # Extract bubbles from cursorDiskKV
        msg_count = 0
        for cid, role, text, db_path in iter_bubbles_from_disk_kv(global_db):
            sessions[cid]["messages"].append({"role": role, "content": text})
            # Record the database path
            if "db_path" not in sessions[cid]:
                sessions[cid]["db_path"] = db_path
            msg_count += 1
            if cid not in comp_meta:
                comp_meta[cid] = {"title": f"Chat {cid[:8]}", "createdAt": None, "lastUpdatedAt": None}
                comp2ws[cid] = "(global)"
        logger.debug(f"  - Extracted {msg_count} messages from global cursorDiskKV bubbles")
        
        # Extract composer data
        comp_count = 0
        for cid, data, db_path in iter_composer_data(global_db):
            if cid not in comp_meta:
                created_at = data.get("createdAt")
                comp_meta[cid] = {
                    "title": f"Chat {cid[:8]}",
                    "createdAt": created_at,
                    "lastUpdatedAt": created_at
                }
                comp2ws[cid] = "(global)"
            
            # Record the database path
            if "db_path" not in sessions[cid]:
                sessions[cid]["db_path"] = db_path
                
            # Extract conversation from composer data
            conversation = data.get("conversation", [])
            if conversation:
                msg_count = 0
                for msg in conversation:
                    msg_type = msg.get("type")
                    if msg_type is None:
                        continue
                    
                    # Type 1 = user, Type 2 = assistant
                    role = "user" if msg_type == 1 else "assistant"
                    content = msg.get("text", "")
                    if content and isinstance(content, str):
                        sessions[cid]["messages"].append({"role": role, "content": content})
                        msg_count += 1
                
                if msg_count > 0:
                    comp_count += 1
                    logger.debug(f"  - Added {msg_count} messages from composer {cid[:8]}")
        
        if comp_count > 0:
            logger.debug(f"  - Extracted data from {comp_count} composers in global cursorDiskKV")
        
        # Also try ItemTable in global DB
        try:
            con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
            chat_data = j(con.cursor(), "ItemTable", "workbench.panel.aichat.view.aichat.chatdata")
            if chat_data:
                msg_count = 0
                for tab in chat_data.get("tabs", []):
                    tab_id = tab.get("tabId")
                    if tab_id and tab_id not in comp_meta:
                        comp_meta[tab_id] = {
                            "title": f"Global Chat {tab_id[:8]}",
                            "createdAt": None,
                            "lastUpdatedAt": None
                        }
                        comp2ws[tab_id] = "(global)"
                    
                    for bubble in tab.get("bubbles", []):
                        content = ""
                        if "text" in bubble:
                            content = bubble["text"]
                        elif "content" in bubble:
                            content = bubble["content"]
                        
                        if content and isinstance(content, str):
                            role = "user" if bubble.get("type") == "user" else "assistant"
                            sessions[tab_id]["messages"].append({"role": role, "content": content})
                            msg_count += 1
                logger.debug(f"  - Extracted {msg_count} messages from global chat data")
            con.close()
        except Exception as e:
            logger.debug(f"Error processing global ItemTable: {e}")

    # 3. Build final list
    out = []
    for cid, data in sessions.items():
        if not data["messages"]:
            continue
        ws_id = comp2ws.get(cid, "(unknown)")
        project = ws_proj.get(ws_id, {"name": "(unknown)", "rootPath": "(unknown)"})
        meta = comp_meta.get(cid, {"title": "(untitled)", "createdAt": None, "lastUpdatedAt": None})
        
        # Create the output object with the db_path included
        chat_data = {
            "project": project,
            "session": {"composerId": cid, **meta},
            "messages": data["messages"],
            "workspace_id": ws_id,
        }
        
        # Add the database path if available
        if "db_path" in data:
            chat_data["db_path"] = data["db_path"]
            
        out.append(chat_data)
    
    # Sort by last updated time if available
    out.sort(key=lambda s: s["session"].get("lastUpdatedAt") or 0, reverse=True)
    logger.debug(f"Total chat sessions extracted: {len(out)}")
    return out

def extract_project_from_git_repos(workspace_id, debug=False):
    """
    Extract project name from the git repositories in a workspace.
    Returns None if no repositories found or unable to access the DB.
    """
    if not workspace_id or workspace_id == "unknown" or workspace_id == "(unknown)" or workspace_id == "(global)":
        if debug:
            logger.debug(f"Invalid workspace ID: {workspace_id}")
        return None
        
    # Find the workspace DB
    cursor_base = cursor_root()
    workspace_db_path = cursor_base / "User" / "workspaceStorage" / workspace_id / "state.vscdb"
    
    if not workspace_db_path.exists():
        if debug:
            logger.debug(f"Workspace DB not found for ID: {workspace_id}")
        return None
        
    try:
        # Connect to the workspace DB
        if debug:
            logger.debug(f"Connecting to workspace DB: {workspace_db_path}")
        con = sqlite3.connect(f"file:{workspace_db_path}?mode=ro", uri=True)
        cur = con.cursor()
        
        # Look for git repositories
        git_data = j(cur, "ItemTable", "scm:view:visibleRepositories")
        if not git_data or not isinstance(git_data, dict) or 'all' not in git_data:
            if debug:
                logger.debug(f"No git repositories found in workspace {workspace_id}, git_data: {git_data}")
            con.close()
            return None
            
        # Extract repo paths from the 'all' key
        repos = git_data.get('all', [])
        if not repos or not isinstance(repos, list):
            if debug:
                logger.debug(f"No repositories in 'all' key for workspace {workspace_id}, repos: {repos}")
            con.close()
            return None
            
        if debug:
            logger.debug(f"Found {len(repos)} git repositories in workspace {workspace_id}: {repos}")
            
        # Process each repo path
        for repo in repos:
            if not isinstance(repo, str):
                continue
                
            # Look for git:Git:file:/// pattern
            if "git:Git:file:///" in repo:
                # Extract the path part
                path = repo.split("file:///")[-1]
                path_parts = [p for p in path.split('/') if p]
                
                if path_parts:
                    # Use the last part as the project name
                    project_name = path_parts[-1]
                    if debug:
                        logger.debug(f"Found project name '{project_name}' from git repo in workspace {workspace_id}")
                    con.close()
                    return project_name
            else:
                if debug:
                    logger.debug(f"No 'git:Git:file:///' pattern in repo: {repo}")
                    
        if debug:
            logger.debug(f"No suitable git repos found in workspace {workspace_id}")
        con.close()
    except Exception as e:
        if debug:
            logger.debug(f"Error extracting git repos from workspace {workspace_id}: {e}")
        return None
        
    return None

def format_chat_for_frontend(chat):
    """Format the chat data to match what the frontend expects."""
    try:
        # Generate a unique ID for this chat if it doesn't have one
        session_id = str(uuid.uuid4())
        if 'session' in chat and chat['session'] and isinstance(chat['session'], dict):
            session_id = chat['session'].get('composerId', session_id)
        
        # Format date from createdAt timestamp or use current date
        date = int(datetime.datetime.now().timestamp())
        if 'session' in chat and chat['session'] and isinstance(chat['session'], dict):
            created_at = chat['session'].get('createdAt')
            if created_at and isinstance(created_at, (int, float)):
                # Check if timestamp is in milliseconds or seconds
                # Timestamps > 10^10 are likely in milliseconds
                # Timestamps < 10^10 are likely in seconds
                if created_at > 10000000000:
                    # Convert from milliseconds to seconds
                    date = created_at / 1000
                else:
                    # Already in seconds
                    date = created_at
        
        # Ensure project has expected fields
        project = chat.get('project', {})
        if not isinstance(project, dict):
            project = {}
            
        # Get workspace_id from chat
        workspace_id = chat.get('workspace_id', 'unknown')
        
        # Get the database path information
        db_path = chat.get('db_path', 'Unknown database path')
        
        # If project name is a username or unknown, try to extract a better name from rootPath
        if project.get('rootPath'):
            current_name = project.get('name', '')
            username = os.path.basename(os.path.expanduser('~'))
            
            # Check if project name is username or unknown or very generic
            if (current_name == username or 
                current_name == '(unknown)' or 
                current_name == 'Root' or
                # Check if rootPath is directly under /Users/username with no additional path components
                (project.get('rootPath').startswith(f'/Users/{username}') and 
                 project.get('rootPath').count('/') <= 3)):
                
                # Try to extract a better name from the path
                project_name = extract_project_name_from_path(project.get('rootPath'), debug=False)
                
                # Only use the new name if it's meaningful
                if (project_name and 
                    project_name != 'Unknown Project' and 
                    project_name != username and
                    project_name not in ['Documents', 'Downloads', 'Desktop']):
                    
                    logger.debug(f"Improved project name from '{current_name}' to '{project_name}'")
                    project['name'] = project_name
                elif project.get('rootPath').startswith(f'/Users/{username}/Documents/codebase/'):
                    # Special case for /Users/saharmor/Documents/codebase/X
                    parts = project.get('rootPath').split('/')
                    if len(parts) > 5:  # /Users/username/Documents/codebase/X
                        project['name'] = parts[5]
                        logger.debug(f"Set project name to specific codebase subdirectory: {parts[5]}")
                    else:
                        project['name'] = "cursor-view"  # Current project as default
        
        # If the project doesn't have a rootPath or it's very generic, enhance it with workspace_id
        if not project.get('rootPath') or project.get('rootPath') == '/' or project.get('rootPath') == '/Users':
            if workspace_id != 'unknown':
                # Use workspace_id to create a more specific path
                if not project.get('rootPath'):
                    project['rootPath'] = f"/workspace/{workspace_id}"
                elif project.get('rootPath') == '/' or project.get('rootPath') == '/Users':
                    project['rootPath'] = f"{project['rootPath']}/workspace/{workspace_id}"
        
        # FALLBACK: If project name is still generic, try to extract it from git repositories
        if project.get('name') in ['Home Directory', '(unknown)']:
            git_project_name = extract_project_from_git_repos(workspace_id, debug=True)
            if git_project_name:
                logger.debug(f"Improved project name from '{project.get('name')}' to '{git_project_name}' using git repo")
                project['name'] = git_project_name
        
        # Add workspace_id to the project data explicitly
        project['workspace_id'] = workspace_id
            
        # Ensure messages exist and are properly formatted
        messages = chat.get('messages', [])
        if not isinstance(messages, list):
            messages = []
        
        # Create properly formatted chat object
        formatted_chat = {
            'project': project,
            'messages': messages,
            'date': date,
            'session_id': session_id,
            'workspace_id': workspace_id,
            'db_path': db_path  # Include the database path in the output
        }

        # Preserve source field if it exists
        if 'source' in chat:
            formatted_chat['source'] = chat['source']

        return formatted_chat
    except Exception as e:
        logger.error(f"Error formatting chat: {e}")
        # Return a minimal valid object if there's an error
        return {
            'project': {'name': 'Error', 'rootPath': '/'},
            'messages': [],
            'date': int(datetime.datetime.now().timestamp()),
            'session_id': str(uuid.uuid4()),
            'workspace_id': 'error',
            'db_path': 'Error retrieving database path'
        }

@app.route('/api/chats', methods=['GET'])
def get_chats():
    """Get all chat sessions with optional data source selection."""
    try:
        # 获取数据源参数，默认为cursor
        source = request.args.get('source', 'cursor').lower()
        if source not in ['cursor', 'augment', 'cursor-augment', 'idea-augment', 'pycharm-augment']:
            return jsonify({"error": "Invalid source. Must be 'cursor', 'augment', 'cursor-augment', 'idea-augment', or 'pycharm-augment'"}), 400

        logger.info(f"Received request for {source} chats from {request.remote_addr}")
        chats = extract_chats(source=source)
        logger.info(f"Retrieved {len(chats)} {source} chats")
        
        # Format each chat for the frontend
        formatted_chats = []
        for chat in chats:
            try:
                formatted_chat = format_chat_for_frontend(chat)
                formatted_chats.append(formatted_chat)
            except Exception as e:
                logger.error(f"Error formatting individual chat: {e}")
                # Skip this chat if it can't be formatted
                continue
        
        logger.info(f"Returning {len(formatted_chats)} formatted chats")
        return jsonify(formatted_chats)
    except Exception as e:
        logger.error(f"Error in get_chats: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/<session_id>', methods=['GET'])
def get_chat(session_id):
    """Get a specific chat session by ID with optional data source selection."""
    try:
        # 获取数据源参数，默认为cursor
        source = request.args.get('source', 'cursor').lower()
        if source not in ['cursor', 'augment', 'cursor-augment', 'idea-augment', 'pycharm-augment']:
            return jsonify({"error": "Invalid source. Must be 'cursor', 'augment', 'cursor-augment', 'idea-augment', or 'pycharm-augment'"}), 400

        logger.info(f"Received request for {source} chat {session_id} from {request.remote_addr}")
        chats = extract_chats(source=source)
        
        for chat in chats:
            # Check for a matching composerId safely
            if 'session' in chat and chat['session'] and isinstance(chat['session'], dict):
                if chat['session'].get('composerId') == session_id:
                    formatted_chat = format_chat_for_frontend(chat)
                    return jsonify(formatted_chat)
        
        logger.warning(f"Chat with ID {session_id} not found")
        return jsonify({"error": "Chat not found"}), 404
    except Exception as e:
        logger.error(f"Error in get_chat: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/<session_id>/export', methods=['GET'])
def export_chat(session_id):
    """Export a specific chat session as standalone HTML or JSON with optional data source selection."""
    try:
        # 获取数据源参数，默认为cursor
        source = request.args.get('source', 'cursor').lower()
        if source not in ['cursor', 'augment', 'cursor-augment', 'idea-augment', 'pycharm-augment']:
            return jsonify({"error": "Invalid source. Must be 'cursor', 'augment', 'cursor-augment', 'idea-augment', or 'pycharm-augment'"}), 400

        logger.info(f"Received request to export {source} chat {session_id} from {request.remote_addr}")
        export_format = request.args.get('format', 'html').lower()
        chats = extract_chats(source=source)
        
        for chat in chats:
            # Check for a matching composerId safely
            if 'session' in chat and chat['session'] and isinstance(chat['session'], dict):
                if chat['session'].get('composerId') == session_id:
                    formatted_chat = format_chat_for_frontend(chat)
                    
                    if export_format == 'json':
                        # Export as JSON
                        return Response(
                            json.dumps(formatted_chat, indent=2),
                            mimetype="application/json; charset=utf-8",
                            headers={
                                "Content-Disposition": f'attachment; filename="cursor-chat-{session_id[:8]}.json"',
                                "Cache-Control": "no-store",
                            },
                        )
                    elif export_format == 'markdown':
                        # Export as Markdown
                        markdown_content = generate_standalone_markdown(formatted_chat)
                        return Response(
                            markdown_content,
                            mimetype="text/markdown; charset=utf-8",
                            headers={
                                "Content-Disposition": f'attachment; filename="cursor-chat-{session_id[:8]}.md"',
                                "Content-Length": str(len(markdown_content)),
                                "Cache-Control": "no-store",
                            },
                        )
                    else:
                        # Default to HTML export
                        html_content = generate_standalone_html(formatted_chat)
                        return Response(
                            html_content,
                            mimetype="text/html; charset=utf-8",
                            headers={
                                "Content-Disposition": f'attachment; filename="cursor-chat-{session_id[:8]}.html"',
                                "Content-Length": str(len(html_content)),
                                "Cache-Control": "no-store",
                            },
                        )
        
        logger.warning(f"Chat with ID {session_id} not found for export")
        return jsonify({"error": "Chat not found"}), 404
    except Exception as e:
        logger.error(f"Error in export_chat: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def generate_standalone_html(chat):
    """Generate a standalone HTML representation of the chat."""
    logger.info(f"Generating HTML for session ID: {chat.get('session_id', 'N/A')}")
    try:
        # Format date for display
        date_display = "Unknown date"
        if chat.get('date'):
            try:
                date_obj = datetime.datetime.fromtimestamp(chat['date'])
                date_display = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.warning(f"Error formatting date: {e}")
        
        # Get project info
        project_name = chat.get('project', {}).get('name', 'Unknown Project')
        project_path = chat.get('project', {}).get('rootPath', 'Unknown Path')
        logger.info(f"Project: {project_name}, Path: {project_path}, Date: {date_display}")
        
        # Build the HTML content
        messages_html = ""
        messages = chat.get('messages', [])
        logger.info(f"Found {len(messages)} messages for the chat.")
        
        if not messages:
            logger.warning("No messages found in the chat object to generate HTML.")
            messages_html = "<p>No messages found in this conversation.</p>"
        else:
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                logger.debug(f"Processing message {i+1}/{len(messages)} - Role: {role}, Content length: {len(content)}")
                
                if not content or not isinstance(content, str):
                    logger.warning(f"Message {i+1} has invalid content: {content}")
                    content = "Content unavailable"
                
                # Simple HTML escaping
                escaped_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                # Convert markdown code blocks (handle potential nesting issues simply)
                processed_content = ""
                in_code_block = False
                for line in escaped_content.split('\n'):
                    if line.strip().startswith("```"):
                        if not in_code_block:
                            processed_content += "<pre><code>"
                            in_code_block = True
                            # Remove the first ``` marker
                            line = line.strip()[3:] 
                        else:
                            processed_content += "</code></pre>\n"
                            in_code_block = False
                            line = "" # Skip the closing ``` line
                    
                    if in_code_block:
                         # Inside code block, preserve spacing and add line breaks
                        processed_content += line + "\n" 
                    else:
                        # Outside code block, use <br> for newlines
                        processed_content += line + "<br>"
                
                # Close any unclosed code block at the end
                if in_code_block:
                    processed_content += "</code></pre>"
                
                avatar = "👤" if role == "user" else "🤖"
                name = "You" if role == "user" else "Cursor Assistant"
                bg_color = "#f0f7ff" if role == "user" else "#f0fff7"
                border_color = "#3f51b5" if role == "user" else "#00796b"
                
                messages_html += f"""
                <div class="message" style="margin-bottom: 20px;">
                    <div class="message-header" style="display: flex; align-items: center; margin-bottom: 8px;">
                        <div class="avatar" style="width: 32px; height: 32px; border-radius: 50%; background-color: {border_color}; color: white; display: flex; justify-content: center; align-items: center; margin-right: 10px;">
                            {avatar}
                        </div>
                        <div class="sender" style="font-weight: bold;">{name}</div>
                    </div>
                    <div class="message-content" style="padding: 15px; border-radius: 8px; background-color: {bg_color}; border-left: 4px solid {border_color}; margin-left: {0 if role == 'user' else '40px'}; margin-right: {0 if role == 'assistant' else '40px'};">
                        {processed_content} 
                    </div>
                </div>
                """

        # Create the complete HTML document
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cursor Chat - {project_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 20px auto; padding: 20px; border: 1px solid #eee; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #2c3e50; }}
        .header {{ background: linear-gradient(90deg, #f0f7ff 0%, #f0fff7 100%); color: white; padding: 15px 20px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px -20px; }}
        .chat-info {{ display: flex; flex-wrap: wrap; gap: 10px 20px; margin-bottom: 20px; background-color: #f9f9f9; padding: 12px 15px; border-radius: 8px; font-size: 0.9em; }}
        .info-item {{ display: flex; align-items: center; }}
        .info-label {{ font-weight: bold; margin-right: 5px; color: #555; }}
        pre {{ background-color: #eef; padding: 15px; border-radius: 5px; overflow-x: auto; border: 1px solid #ddd; font-family: 'Courier New', Courier, monospace; font-size: 0.9em; white-space: pre-wrap; word-wrap: break-word; }}
        code {{ background-color: transparent; padding: 0; border-radius: 0; font-family: inherit; }}
        .message-content pre code {{ background-color: transparent; }}
        .message-content {{ word-wrap: break-word; overflow-wrap: break-word; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Cursor Chat: {project_name}</h1>
    </div>
    <div class="chat-info">
        <div class="info-item"><span class="info-label">Project:</span> <span>{project_name}</span></div>
        <div class="info-item"><span class="info-label">Path:</span> <span>{project_path}</span></div>
        <div class="info-item"><span class="info-label">Date:</span> <span>{date_display}</span></div>
        <div class="info-item"><span class="info-label">Session ID:</span> <span>{chat.get('session_id', 'Unknown')}</span></div>
    </div>
    <h2>Conversation History</h2>
    <div class="messages">
{messages_html}
    </div>
</body>
</html>"""
        
        logger.info(f"Finished generating HTML. Total length: {len(html)}")
        return html
    except Exception as e:
        logger.error(f"Error generating HTML for session {chat.get('session_id', 'N/A')}: {e}", exc_info=True)
        # Return an HTML formatted error message
        return f"<html><body><h1>Error generating chat export</h1><p>Error: {e}</p></body></html>"

def generate_standalone_markdown(chat):
    """Generate a standalone Markdown representation of the chat."""
    logger.info(f"Generating Markdown for session ID: {chat.get('session_id', 'N/A')}")
    try:
        # Format date for display
        date_display = "Unknown date"
        if chat.get('date'):
            try:
                date_obj = datetime.datetime.fromtimestamp(chat['date'])
                date_display = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.warning(f"Error formatting date: {e}")

        # Get project info
        project_name = chat.get('project', {}).get('name', 'Unknown Project')
        project_path = chat.get('project', {}).get('rootPath', 'Unknown Path')
        session_id = chat.get('session_id', 'Unknown')
        workspace_id = chat.get('workspace_id', 'Unknown')

        logger.info(f"Project: {project_name}, Path: {project_path}, Date: {date_display}")

        # Escape markdown special characters, but preserve code blocks
        def escape_markdown(text):
            """Escape markdown special characters outside of code blocks."""
            if not text or not isinstance(text, str):
                return text

            # Split by code blocks to preserve them
            parts = []
            current_part = ""
            in_code_block = False
            lines = text.split('\n')

            for line in lines:
                if line.strip().startswith("```"):
                    if not in_code_block:
                        # Entering code block - escape the current part and add it
                        if current_part:
                            escaped_part = escape_text_only(current_part.rstrip('\n'))
                            parts.append(escaped_part)
                            current_part = ""
                        parts.append(line)  # Add the opening ``` as-is
                        in_code_block = True
                    else:
                        # Exiting code block
                        parts.append(line)  # Add the closing ``` as-is
                        in_code_block = False
                else:
                    if in_code_block:
                        # Inside code block - preserve as-is
                        parts.append(line)
                    else:
                        # Outside code block - accumulate for escaping
                        current_part += line + '\n'

            # Handle any remaining text outside code blocks
            if current_part and not in_code_block:
                escaped_part = escape_text_only(current_part.rstrip('\n'))
                parts.append(escaped_part)

            return '\n'.join(parts)

        def escape_text_only(text):
            """Escape markdown special characters in regular text."""
            # Escape markdown special characters
            special_chars = ['\\', '*', '_', '#', '[', ']', '(', ')', '|', '`']
            for char in special_chars:
                text = text.replace(char, '\\' + char)
            return text

        # Build the markdown content
        messages = chat.get('messages', [])
        logger.info(f"Found {len(messages)} messages for the chat.")

        # Start building the markdown document
        markdown_content = f"""# Chat Export - {escape_text_only(project_name)}

## Metadata

| Field | Value |
|-------|-------|
| Project | {escape_text_only(project_name)} |
| Path | {escape_text_only(project_path)} |
| Date | {date_display} |
| Session ID | {session_id} |
| Workspace ID | {workspace_id} |

## Conversation

"""

        if not messages:
            logger.warning("No messages found in the chat object to generate Markdown.")
            markdown_content += "No messages found in this conversation.\n"
        else:
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                logger.debug(f"Processing message {i+1}/{len(messages)} - Role: {role}, Content length: {len(content)}")

                if not content or not isinstance(content, str):
                    logger.warning(f"Message {i+1} has invalid content: {content}")
                    content = "Content unavailable"

                # Escape markdown in content while preserving code blocks
                escaped_content = escape_markdown(content)

                # Add role header with emoji
                if role == "user":
                    markdown_content += "### 👤 User\n\n"
                else:
                    markdown_content += "### 🤖 Cursor Assistant\n\n"

                # Add the message content
                markdown_content += escaped_content + "\n\n"

        logger.info(f"Finished generating Markdown. Total length: {len(markdown_content)}")
        return markdown_content
    except Exception as e:
        logger.error(f"Error generating Markdown for session {chat.get('session_id', 'N/A')}: {e}", exc_info=True)
        # Return a markdown formatted error message
        return f"# Error generating chat export\n\nError: {e}\n"

################################################################################
# Configuration API endpoints
################################################################################

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """获取当前配置设置"""
    try:
        logger.info(f"获取配置设置请求来自 {request.remote_addr}")

        # 获取所有路径配置
        paths = config_manager.get_all_paths()

        # 获取配置文件信息
        config_info = config_manager.get_config_info()

        # 获取默认路径
        default_paths = {}
        for data_source in paths.keys():
            default_path = config_manager.get_default_path(data_source)
            default_paths[data_source] = default_path

        response_data = {
            "paths": paths,
            "default_paths": default_paths,
            "config_info": config_info
        }

        logger.info("成功返回配置设置")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"获取配置设置时出错: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """保存配置设置"""
    try:
        logger.info(f"保存配置设置请求来自 {request.remote_addr}")

        data = request.get_json()
        if not data:
            return jsonify({"error": "请求数据为空"}), 400

        paths = data.get('paths', {})
        if not isinstance(paths, dict):
            return jsonify({"error": "路径配置格式无效"}), 400

        # 保存路径配置
        success = config_manager.set_all_paths(paths)

        if success:
            logger.info("配置设置保存成功")
            return jsonify({"message": "配置保存成功", "success": True})
        else:
            logger.error("配置设置保存失败")
            return jsonify({"error": "配置保存失败"}), 500

    except Exception as e:
        logger.error(f"保存配置设置时出错: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/validate', methods=['POST'])
def validate_paths():
    """验证路径配置"""
    try:
        logger.info(f"验证路径请求来自 {request.remote_addr}")

        data = request.get_json()
        if not data:
            return jsonify({"error": "请求数据为空"}), 400

        # 可以验证单个路径或多个路径
        if 'data_source' in data and 'path' in data:
            # 验证单个路径
            data_source = data['data_source']
            path = data['path']

            result = path_validator.validate_path(data_source, path)

            return jsonify({
                "is_valid": result.is_valid,
                "message": result.message,
                "details": result.details,
                "found_files": result.found_files
            })

        elif 'paths' in data:
            # 验证多个路径
            paths = data['paths']
            if not isinstance(paths, dict):
                return jsonify({"error": "路径配置格式无效"}), 400

            results = path_validator.validate_all_paths(paths)

            # 转换结果格式
            response_results = {}
            for data_source, result in results.items():
                response_results[data_source] = {
                    "is_valid": result.is_valid,
                    "message": result.message,
                    "details": result.details,
                    "found_files": result.found_files
                }

            return jsonify({"results": response_results})

        else:
            return jsonify({"error": "请求参数无效"}), 400

    except Exception as e:
        logger.error(f"验证路径时出错: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    """重置配置设置"""
    try:
        logger.info(f"重置配置设置请求来自 {request.remote_addr}")

        data = request.get_json()

        if data and 'data_source' in data:
            # 重置单个数据源
            data_source = data['data_source']
            success = config_manager.reset_path(data_source)

            if success:
                logger.info(f"成功重置{data_source}配置")
                return jsonify({"message": f"成功重置{data_source}配置", "success": True})
            else:
                return jsonify({"error": f"重置{data_source}配置失败"}), 500
        else:
            # 重置所有配置
            success = config_manager.reset_all_paths()

            if success:
                logger.info("成功重置所有配置")
                return jsonify({"message": "成功重置所有配置", "success": True})
            else:
                return jsonify({"error": "重置配置失败"}), 500

    except Exception as e:
        logger.error(f"重置配置设置时出错: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

################################################################################
# Batch Download API Endpoints
################################################################################

@app.route('/api/chats/batch-export', methods=['POST'])
def batch_export_chats():
    """
    创建批量导出任务

    请求体：{
        "session_ids": ["id1", "id2", ...],
        "format": "html|json|markdown",
        "source": "cursor|augment|cursor-augment|idea-augment|pycharm-augment"
    }

    响应：{
        "task_id": "uuid",
        "status": "pending",
        "message": "任务创建成功"
    }
    """
    try:
        logger.info(f"收到批量导出请求，来自 {request.remote_addr}")

        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求数据为空"}), 400

        session_ids = data.get('session_ids', [])
        format_type = data.get('format', 'html').lower()
        source = data.get('source', 'cursor').lower()

        # 验证参数
        if not session_ids:
            return jsonify({"error": "会话ID列表不能为空"}), 400

        if not isinstance(session_ids, list):
            return jsonify({"error": "会话ID必须是列表格式"}), 400

        if len(session_ids) > 100:  # 限制最大数量
            return jsonify({"error": "单次最多只能导出100个会话"}), 400

        if format_type not in ['html', 'json', 'markdown']:
            return jsonify({"error": f"不支持的格式类型: {format_type}"}), 400

        if source not in ['cursor', 'augment', 'cursor-augment', 'idea-augment', 'pycharm-augment']:
            return jsonify({"error": f"不支持的数据源: {source}"}), 400

        # 创建批量下载任务
        task_id = batch_download_manager.create_batch_task(session_ids, format_type, source)

        logger.info(f"批量导出任务创建成功: {task_id}, 会话数: {len(session_ids)}, 格式: {format_type}, 数据源: {source}")

        return jsonify({
            "task_id": task_id,
            "status": "pending",
            "message": "任务创建成功",
            "session_count": len(session_ids)
        })

    except ValueError as e:
        logger.warning(f"批量导出参数错误: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"创建批量导出任务失败: {e}", exc_info=True)
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/batch-download/<task_id>/status', methods=['GET'])
def get_batch_download_status(task_id):
    """
    获取批量下载任务状态

    响应：{
        "task_id": "uuid",
        "status": "pending|processing|completed|failed|cancelled",
        "progress": 0.75,
        "completed_count": 8,
        "total_count": 10,
        "created_at": "2024-01-01T12:00:00",
        "started_at": "2024-01-01T12:00:01",
        "completed_at": "2024-01-01T12:00:30",
        "error_message": null,
        "failed_sessions": [],
        "download_url": "/api/batch-download/uuid/file"
    }
    """
    try:
        logger.debug(f"查询批量下载状态: {task_id}")

        # 获取任务状态
        status_info = batch_download_manager.get_task_status(task_id)

        if not status_info:
            return jsonify({"error": "任务不存在"}), 404

        # 如果任务已完成，添加下载URL
        if status_info['status'] == 'completed':
            status_info['download_url'] = f"/api/batch-download/{task_id}/file"

        return jsonify(status_info)

    except Exception as e:
        logger.error(f"获取批量下载状态失败: {e}", exc_info=True)
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/batch-download/<task_id>/cancel', methods=['POST'])
def cancel_batch_download(task_id):
    """
    取消批量下载任务

    响应：{
        "success": true,
        "message": "任务已取消"
    }
    """
    try:
        logger.info(f"取消批量下载任务: {task_id}")

        success = batch_download_manager.cancel_task(task_id)

        if success:
            return jsonify({
                "success": True,
                "message": "任务已取消"
            })
        else:
            return jsonify({
                "success": False,
                "message": "任务不存在或无法取消"
            }), 400

    except Exception as e:
        logger.error(f"取消批量下载任务失败: {e}", exc_info=True)
        return jsonify({"error": "服务器内部错误"}), 500

@app.route('/api/batch-download/<task_id>/file', methods=['GET'])
def download_batch_file(task_id):
    """
    下载批量导出的文件

    响应：ZIP文件流
    """
    try:
        logger.info(f"下载批量导出文件: {task_id}")

        # 获取文件路径
        file_path = batch_download_manager.get_task_file_path(task_id)

        if not file_path:
            return jsonify({"error": "文件不存在或任务未完成"}), 404

        if not os.path.exists(file_path):
            return jsonify({"error": "文件已被清理或不存在"}), 404

        # 获取任务信息用于生成文件名
        task_info = batch_download_manager.get_task_status(task_id)
        if task_info:
            format_type = task_info.get('format_type', 'unknown')
            source = task_info.get('source', 'unknown')
            filename = f"ai_ide_batch_export_{source}_{format_type}_{task_id[:8]}.zip"
        else:
            filename = f"ai_ide_batch_export_{task_id[:8]}.zip"

        # 返回文件
        return send_from_directory(
            directory=os.path.dirname(file_path),
            path=os.path.basename(file_path),
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )

    except Exception as e:
        logger.error(f"下载批量导出文件失败: {e}", exc_info=True)
        return jsonify({"error": "服务器内部错误"}), 500

# Serve React app
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    if path and Path(app.static_folder, path).exists():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Cursor Chat View server')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    args = parser.parse_args()
    
    logger.info(f"Starting server on port {args.port}")
    app.run(host='127.0.0.1', port=args.port, debug=args.debug)