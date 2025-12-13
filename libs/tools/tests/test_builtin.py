import pytest
import os
from pathlib import Path
from tools.registry import ToolRegistry
from tools.builtin import file, search, shell, http, code_analysis

@pytest.fixture
def registry():
    return ToolRegistry()

def test_builtin_discovery(registry):
    """Test that builtin tools are discovered and registered."""
    registry.discover_builtin()
    
    # Check that tools from each module are registered
    tool_names = registry.list_names()
    
    # File tools
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "list_files" in tool_names
    assert "file_info" in tool_names
    
    # Search tools
    assert "search_codebase" in tool_names
    
    # Shell tools
    assert "run_command" in tool_names
    
    # HTTP tools
    assert "http_request" in tool_names
    
    # Code analysis tools
    assert "parse_ast" in tool_names

def test_file_tools(tmp_path):
    """Test file operations."""
    test_file = tmp_path / "test.txt"
    test_content = "Hello Maven"
    
    # Write
    result = file.write_file(str(test_file), test_content)
    assert "Successfully wrote" in result
    assert test_file.exists()
    
    # Read
    content = file.read_file(str(test_file))
    assert content == test_content
    
    # Info
    info = file.file_info(str(test_file))
    assert info.size == len(test_content)
    assert info.type == ".txt"

def test_search_tools_availability():
    """Test that search tools are available (even if retrieval lib is missing/mocked)."""
    # We just check the function exists and runs
    # Since we can't easily mock the retrieval lib dependency here without more setup,
    # we'll just check the tool creation.
    tools = search.create_tool(None, None)
    assert len(tools) > 0
    names = [t[0].name for t in tools]
    assert "search_codebase" in names

def test_shell_tools():
    """Test shell execution."""
    result = shell.run_command("echo 'hello'", timeout=5)
    assert "hello" in result
    assert "Exit Code: 0" in result

def test_code_analysis_tools(tmp_path):
    """Test code analysis."""
    # Create a dummy python file
    py_file = tmp_path / "hello.py"
    content = """
import os

def hello():
    print("world")

class Greeter:
    def greet(self):
        pass
"""
    py_file.write_text(content)
    
    # Parse AST
    symbols = code_analysis.parse_ast(str(py_file))
    assert len(symbols) == 3  # hello, Greeter, greet
    names = [s.name for s in symbols]
    assert "hello" in names
    assert "Greeter" in names
    assert "greet" in names
    
    # Get imports
    imports = code_analysis.get_imports(str(py_file))
    assert len(imports) == 1
    assert imports[0].module == "os"

