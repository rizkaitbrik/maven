import subprocess
import shlex
import os
from typing import List, Optional, Any, Tuple
from dataclasses import dataclass

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from tools.models.tools import ToolMetadata, ToolConfig, ToolType
from tools.interfaces.logger import LoggerProtocol

class RunCommandInput(BaseModel):
    command: str = Field(..., description="Shell command to execute")
    cwd: Optional[str] = Field(None, description="Current working directory")
    timeout: int = Field(30, description="Timeout in seconds")

class RunScriptInput(BaseModel):
    script_path: str = Field(..., description="Path to script")
    args: List[str] = Field(default_factory=list, description="Arguments for the script")

def run_command(command: str, cwd: Optional[str] = None, timeout: int = 30) -> str:
    """Run a shell command."""
    try:
        # Security warning: This allows arbitrary code execution.
        args = shlex.split(command)
        result = subprocess.run(
            args,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True
        )
        
        output = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
            
        return output
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error executing command: {str(e)}"

def run_script(script_path: str, args: List[str] = []) -> str:
    """Run a script file."""
    try:
        if not os.path.exists(script_path):
            return f"Script not found: {script_path}"
            
        cmd = [script_path] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
         
        output = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
            
        return output
    except Exception as e:
        return f"Error running script: {str(e)}"

def create_tool(config: ToolConfig, logger: LoggerProtocol) -> List[Tuple[BaseTool, ToolMetadata]]:
    tools = []
    
    tools.append((
        StructuredTool.from_function(
            func=run_command,
            name="run_command",
            description="Run a shell command.",
            args_schema=RunCommandInput
        ),
        ToolMetadata(category=ToolType.DEVELOPMENT, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=run_script,
            name="run_script",
            description="Run a local script.",
            args_schema=RunScriptInput
        ),
        ToolMetadata(category=ToolType.DEVELOPMENT, requires_auth=False)
    ))
    
    return tools

