import ast
import os
from typing import List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from tools.models.tools import ToolMetadata, ToolConfig, ToolType
from tools.interfaces.logger import LoggerProtocol

# Models
class ParseAstInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to parse")
    language: str = Field("python", description="Language of the file (only python supported for deep analysis)")

class FindDefinitionInput(BaseModel):
    symbol_name: str = Field(..., description="Name of the symbol (function/class) to find")
    directory: str = Field(..., description="Directory to search in")

class FindUsagesInput(BaseModel):
    symbol_name: str = Field(..., description="Name of the symbol to find usages of")
    directory: str = Field(..., description="Directory to search in")

class GetImportsInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to get imports from")

# Dataclasses for results
@dataclass
class SymbolInfo:
    name: str
    type: str # function, class
    lineno: int
    col_offset: int

@dataclass
class ImportInfo:
    module: str
    alias: Optional[str] = None
    names: List[str] = field(default_factory=list)

# Implementation
def parse_ast(file_path: str, language: str = "python") -> Union[List[SymbolInfo], str]:
    """Parse file and return functions/classes."""
    if language.lower() != "python":
        return "Only Python is supported for AST parsing currently."
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content)
        symbols = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                symbols.append(SymbolInfo(node.name, "function", node.lineno, node.col_offset))
            elif isinstance(node, ast.ClassDef):
                symbols.append(SymbolInfo(node.name, "class", node.lineno, node.col_offset))
        
        return symbols
    except Exception as e:
        return f"Error parsing AST: {str(e)}"

def find_definition(symbol_name: str, directory: str) -> Union[List[str], str]:
    """Find definition of a symbol in a directory."""
    try:
        definitions = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == symbol_name:
                                definitions.append(f"{path}:{node.lineno}")
                    except:
                        continue
        return definitions
    except Exception as e:
        return f"Error finding definition: {str(e)}"

def find_usages(symbol_name: str, directory: str) -> Union[List[str], str]:
    """Find usages of a symbol in a directory (naive search)."""
    try:
        usages = []
        for root, _, files in os.walk(directory):
            for file in files:
                # Text based search for now
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for i, line in enumerate(lines):
                        if symbol_name in line:
                            usages.append(f"{path}:{i+1}")
                except:
                    continue
        return usages
    except Exception as e:
        return f"Error finding usages: {str(e)}"

def get_imports(file_path: str) -> Union[List[ImportInfo], str]:
    """Get imports from a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        tree = ast.parse(content)
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(ImportInfo(module=name.name, alias=name.asname))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [n.name for n in node.names]
                imports.append(ImportInfo(module=module, names=names))
                
        return imports
    except Exception as e:
        return f"Error getting imports: {str(e)}"

def create_tool(config: ToolConfig, logger: LoggerProtocol) -> List[Tuple[BaseTool, ToolMetadata]]:
    tools = []
    
    tools.append((
        StructuredTool.from_function(
            func=parse_ast,
            name="parse_ast",
            description="Parse a Python file and return classes/functions.",
            args_schema=ParseAstInput
        ),
        ToolMetadata(category=ToolType.ANALYSIS, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=find_definition,
            name="find_definition",
            description="Find definition of a symbol.",
            args_schema=FindDefinitionInput
        ),
        ToolMetadata(category=ToolType.ANALYSIS, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=find_usages,
            name="find_usages",
            description="Find usages of a symbol (naive text search).",
            args_schema=FindUsagesInput
        ),
        ToolMetadata(category=ToolType.ANALYSIS, requires_auth=False)
    ))
    
    tools.append((
        StructuredTool.from_function(
            func=get_imports,
            name="get_imports",
            description="Get imports from a Python file.",
            args_schema=GetImportsInput
        ),
        ToolMetadata(category=ToolType.ANALYSIS, requires_auth=False)
    ))
    
    return tools

