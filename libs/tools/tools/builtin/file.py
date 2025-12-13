import os
import shutil
from pathlib import Path
from typing import List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from datetime import datetime

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from tools.models.tools import ToolMetadata, ToolConfig, ToolType
from tools.interfaces.logger import LoggerProtocol

# Validation Models
class ReadFileInput(BaseModel):
    path: str = Field(..., description="Path to the file to read")

class WriteFileInput(BaseModel):
    path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")

class ListFilesInput(BaseModel):
    directory: str = Field(..., description="Directory to list files in")
    pattern: str = Field("*", description="Glob pattern to filter files")

class FileInfoInput(BaseModel):
    path: str = Field(..., description="Path to the file to get info for")

class MoveFileInput(BaseModel):
    source: str = Field(..., description="Source file path")
    destination: str = Field(..., description="Destination file path")

class CopyFileInput(BaseModel):
    source: str = Field(..., description="Source file path")
    destination: str = Field(..., description="Destination file path")

# Implementation
def read_file(path: str) -> str:
    """Read contents of a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_files(directory: str, pattern: str = "*") -> List[str]:
    """List files in a directory matching a pattern."""
    try:
        p = Path(directory)
        if not p.exists():
            return [f"Directory not found: {directory}"]
        return [str(f) for f in p.glob(pattern)]
    except Exception as e:
        return [f"Error listing files: {str(e)}"]

@dataclass
class FileInfo:
    size: int
    type: str
    last_modified: str

def file_info(path: str) -> Union[FileInfo, str]:
    """Get information about a file."""
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        stat = p.stat()
        file_type = "directory" if p.is_dir() else "file"
        # Determine extension if file
        if p.is_file() and p.suffix:
             file_type = p.suffix
        
        return FileInfo(
            size=stat.st_size,
            type=file_type,
            last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
        )
    except Exception as e:
        return f"Error getting file info: {str(e)}"

def move_file(source: str, destination: str) -> str:
    """Move a file from source to destination."""
    try:
        shutil.move(source, destination)
        return f"Successfully moved {source} to {destination}"
    except Exception as e:
        return f"Error moving file: {str(e)}"

def copy_file(source: str, destination: str) -> str:
    """Copy a file from source to destination."""
    try:
        shutil.copy2(source, destination)
        return f"Successfully copied {source} to {destination}"
    except Exception as e:
        return f"Error copying file: {str(e)}"

def create_tool(config: ToolConfig, logger: LoggerProtocol) -> List[Tuple[BaseTool, ToolMetadata]]:
    tools = []
    
    # Read File
    tools.append((
        StructuredTool.from_function(
            func=read_file,
            name="read_file",
            description="Read the contents of a file at the given path.",
            args_schema=ReadFileInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    # Write File
    tools.append((
        StructuredTool.from_function(
            func=write_file,
            name="write_file",
            description="Write content to a file at the given path.",
            args_schema=WriteFileInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    # List Files
    tools.append((
        StructuredTool.from_function(
            func=list_files,
            name="list_files",
            description="List files in a directory matching a pattern.",
            args_schema=ListFilesInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    # File Info
    tools.append((
        StructuredTool.from_function(
            func=file_info,
            name="file_info",
            description="Get information about a file (size, type, last modified).",
            args_schema=FileInfoInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    # Move File
    tools.append((
        StructuredTool.from_function(
            func=move_file,
            name="move_file",
            description="Move a file from source to destination.",
            args_schema=MoveFileInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    # Copy File
    tools.append((
        StructuredTool.from_function(
            func=copy_file,
            name="copy_file",
            description="Copy a file from source to destination.",
            args_schema=CopyFileInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))

    return tools

