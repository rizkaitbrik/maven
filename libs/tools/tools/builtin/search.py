import asyncio
from typing import List, Optional, Any, Tuple
from dataclasses import dataclass

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from tools.models.tools import ToolMetadata, ToolConfig, ToolType
from tools.interfaces.logger import LoggerProtocol

try:
    from retrieval.models.search import SearchRequest
    from retrieval.models.config import RetrieverConfig
    from retrieval.adapters.spotlight import SpotlightAdapter
    HAS_RETRIEVAL = True
except ImportError:
    HAS_RETRIEVAL = False

# Models
class SearchCodebaseInput(BaseModel):
    query: str = Field(..., description="Query string to search for")
    top_k: int = Field(5, description="Number of results to return")
    filter_path: Optional[str] = Field(None, description="Path to filter results by")

class SearchByFileTypeInput(BaseModel):
    query: str = Field(..., description="Query string to search for")
    file_types: List[str] = Field(..., description="List of file extensions to include (e.g. ['.py', '.js'])")

class SearchByContentInput(BaseModel):
    query: str = Field(..., description="Content string to search for")

# Async Implementations
async def _search_async(query: str, top_k: int = 5, filter_path: Optional[str] = None) -> str:
    if not HAS_RETRIEVAL:
        return "Search functionality not available (libs/retrieval not found)."
    
    try:
        config = RetrieverConfig()
        if filter_path:
            config.allowed_list = [filter_path]
            
        adapter = SpotlightAdapter(config=config)
        request = SearchRequest(query=query, size=top_k)
        
        response = await adapter.search(request)
        
        if not response.results:
            return "No results found."
            
        return "\n".join([f"{r.path}" for r in response.results])
    except Exception as e:
        return f"Search error: {str(e)}"

# Sync Wrappers
def search_codebase(query: str, top_k: int = 5, filter_path: Optional[str] = None) -> str:
    """Search the codebase using system search."""
    return asyncio.run(_search_async(query, top_k, filter_path))

async def search_codebase_async(query: str, top_k: int = 5, filter_path: Optional[str] = None) -> str:
    return await _search_async(query, top_k, filter_path)

def search_by_file_type(query: str, file_types: List[str]) -> str:
    """Search for query in specific file types."""
    # Construct mdfind-friendly query
    ext_query = " OR ".join([f'name:"*{ext}"' for ext in file_types])
    full_query = f'{query} ({ext_query})'
    return asyncio.run(_search_async(full_query))

async def search_by_file_type_async(query: str, file_types: List[str]) -> str:
    ext_query = " OR ".join([f'name:"*{ext}"' for ext in file_types])
    full_query = f'{query} ({ext_query})'
    return await _search_async(full_query)

def search_by_content(query: str) -> str:
    """Search file content."""
    return asyncio.run(_search_async(query))

async def search_by_content_async(query: str) -> str:
    return await _search_async(query)

def create_tool(config: ToolConfig, logger: LoggerProtocol) -> List[Tuple[BaseTool, ToolMetadata]]:
    tools = []
    
    tools.append((
        StructuredTool.from_function(
            func=search_codebase,
            coroutine=search_codebase_async,
            name="search_codebase",
            description="Search the codebase using system search.",
            args_schema=SearchCodebaseInput
        ),
        ToolMetadata(category=ToolType.SEARCH, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=search_by_file_type,
            coroutine=search_by_file_type_async,
            name="search_by_file_type",
            description="Search by file type.",
            args_schema=SearchByFileTypeInput
        ),
        ToolMetadata(category=ToolType.SEARCH, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=search_by_content,
            coroutine=search_by_content_async,
            name="search_by_content",
            description="Search file content.",
            args_schema=SearchByContentInput
        ),
        ToolMetadata(category=ToolType.SEARCH, requires_auth=False)
    ))
    
    return tools

