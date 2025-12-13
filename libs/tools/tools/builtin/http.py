import requests
from typing import List, Optional, Any, Tuple, Dict
from dataclasses import dataclass

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from tools.models.tools import ToolMetadata, ToolConfig, ToolType
from tools.interfaces.logger import LoggerProtocol

class HttpRequestInput(BaseModel):
    url: str = Field(..., description="URL to send request to")
    method: str = Field("GET", description="HTTP method (GET, POST, PUT, DELETE, etc.)")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    body: Optional[Any] = Field(None, description="Request body (JSON/text)")

class FetchJsonInput(BaseModel):
    url: str = Field(..., description="URL to fetch JSON from")

def http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: Optional[Any] = None) -> str:
    """Send an HTTP request."""
    try:
        response = requests.request(method=method, url=url, headers=headers, json=body)
        return f"Status: {response.status_code}\nContent: {response.text}"
    except Exception as e:
        return f"Error sending request: {str(e)}"

def fetch_json(url: str) -> str:
    """Fetch JSON from a URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error fetching JSON: {str(e)}"

def create_tool(config: ToolConfig, logger: LoggerProtocol) -> List[Tuple[BaseTool, ToolMetadata]]:
    tools = []
    
    tools.append((
        StructuredTool.from_function(
            func=http_request,
            name="http_request",
            description="Send an HTTP request.",
            args_schema=HttpRequestInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=fetch_json,
            name="fetch_json",
            description="Fetch JSON from a URL.",
            args_schema=FetchJsonInput
        ),
        ToolMetadata(category=ToolType.DATA, requires_auth=False)
    ))
    
    return tools

