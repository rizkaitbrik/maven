import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, Optional, List, Any

from langchain.tools import BaseTool

from maven_logging import Logger
from tools.interfaces.logger import LoggerProtocol
from tools.models.tools import ToolMetadata, ToolConfig, ToolType


def safe_log(logger: LoggerProtocol | logging.Logger, level: str, msg: str, **kwargs):
    """
    Safely log with kwargs if supported, fallback to formatted string.

    This handles both Maven Logger (supports kwargs) and stdlib Logger.
    """
    log_method = getattr(logger, level.lower())

    try:
        # Try with kwargs (Maven Logger)
        log_method(msg, **kwargs)
    except TypeError:
        # Fallback to formatted string (stdlib Logger)
        if kwargs:
            formatted_kwargs = " ".join(f"{k}={v}" for k, v in kwargs.items())
            log_method(f"{msg} {formatted_kwargs}")
        else:
            log_method(msg)


class ToolRegistry:
    """
    Central registry for all Maven tools.
    Manages tool discovery, registration, and lifecycle.
    """

    def __init__(self, logger: Optional[LoggerProtocol] = None):
        """Initialize the tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        self._metadata: Dict[str, ToolMetadata] = {}

        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger("tools.registry")
            self.logger.setLevel(logging.INFO)

    def register(
            self,
            tool: BaseTool,
            metadata: ToolMetadata
    ) -> None:
        """Register a LangChain tool with Maven metadata."""
        tool_name = tool.name

        if tool_name in self._tools:
            safe_log(
                self.logger,
                "warning",
                f"Tool '{tool_name}' already registered, overwriting",
                tool_name=tool_name
            )

        self._tools[tool_name] = tool
        self._metadata[tool_name] = metadata

        safe_log(
            self.logger,
            "info",
            "Registered tool",
            tool_name=tool_name,
            category=metadata.category.value,
            requires_auth=metadata.requires_auth
        )

    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        tool = self._tools.get(name)
        if not tool:
            safe_log(
                self.logger,
                "warning",
                "Tool not found",
                tool_name=name
            )
        return tool

    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """
        Get Maven metadata for a tool.

        Args:
            name: Tool name

        Returns:
            Tool metadata or None if not found
        """
        return self._metadata.get(name)

    def list_all(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def list_by_category(self, category: ToolType) -> List[BaseTool]:
        """
        Get tools filtered by category (ToolType).

        Args:
            category: Tool category/type to filter by

        Returns:
            List of tools in the specified category
        """
        tools = [
            tool for name, tool in self._tools.items()
            if self._metadata[name].category == category
        ]

        safe_log(
            self.logger,
            "debug",
            "Listed tools by category",
            category=category.value,
            count=len(tools)
        )

        return tools

    def list_names(self) -> List[str]:
        """Get all tool names."""
        return list(self._tools.keys())

    def discover_builtin(
            self,
            config: Optional[Dict[str, ToolConfig]] = None
    ) -> None:
        """
        Auto-discover tools in tools/builtin/ and register them.

        Args:
            config: Tool-specific configurations (dict of tool_name -> ToolConfig)
        """
        config = config or {}
        builtin_path = Path(__file__).parent / "builtin"

        if not builtin_path.exists():
            safe_log(
                self.logger,
                "error",
                "Builtin tools directory not found",
                path=str(builtin_path)
            )
            return

        safe_log(
            self.logger,
            "info",
            "Starting builtin tool discovery",
            path=str(builtin_path)
        )

        discovered_count = 0
        failed_count = 0

        # Import all modules in builtin/
        for module_info in pkgutil.iter_modules([str(builtin_path)]):
            if module_info.name.startswith("_"):
                continue  # Skip private modules

            module_name = f"tools.builtin.{module_info.name}"

            try:
                module = importlib.import_module(module_name)

                # Look for create_tool() function in each module
                if not hasattr(module, "create_tool"):
                    safe_log(
                        self.logger,
                        "warning",
                        "Module missing create_tool function",
                        module=module_name
                    )
                    continue

                # Get config for this tool, or use default
                tool_config = config.get(module_info.name, ToolConfig())

                if not tool_config.enabled:
                    safe_log(
                        self.logger,
                        "info",
                        "Skipping disabled tool",
                        tool_module=module_info.name
                    )
                    continue

                # Create child logger for the tool
                tool_logger = self._create_child_logger(
                    f"tools.{module_info.name}"
                )

                # Call create_tool factory function
                result = module.create_tool(tool_config, tool_logger)
                
                if isinstance(result, list):
                    for tool, metadata in result:
                        self.register(tool, metadata)
                        discovered_count += 1
                else:
                    tool, metadata = result
                    self.register(tool, metadata)
                    discovered_count += 1

            except Exception as e:
                failed_count += 1
                safe_log(
                    self.logger,
                    "error",
                    f"Failed to load tool from {module_name}",
                    module=module_name,
                    error=str(e)
                )

        safe_log(
            self.logger,
            "info",
            "Tool discovery complete",
            discovered=discovered_count,
            failed=failed_count,
            total_registered=len(self._tools)
        )

    def _create_child_logger(self, name: str) -> Logger | Logger:
        """
        Create a child logger for a tool.

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        # Check if we're using Maven logger
        logger_module = type(self.logger).__module__

        if "maven_logging" in logger_module:
            # Use Maven's get_logger
            try:
                from maven_logging import get_logger
                return get_logger(name)
            except ImportError:
                pass

        # Fallback to stdlib logger
        child_logger = logging.getLogger(name)
        if not child_logger.handlers:
            # Copy parent's level
            if hasattr(self.logger, 'level'):
                child_logger.setLevel(self.logger.level)
            else:
                child_logger.setLevel(logging.INFO)
        return child_logger

    def validate_auth(self) -> Dict[str, bool]:
        """
        Check if all tools requiring auth have valid credentials.

        Returns:
            Dict mapping tool names to auth validity status
        """
        safe_log(self.logger, "info", "Validating tool authentication")

        results = {}

        for name, tool in self._tools.items():
            metadata = self._metadata[name]

            if not metadata.requires_auth:
                results[name] = True
                continue

            if hasattr(tool, "validate_auth"):
                try:
                    is_valid = tool.validate_auth()
                    results[name] = is_valid

                    if not is_valid:
                        safe_log(
                            self.logger,
                            "warning",
                            "Tool authentication failed",
                            tool_name=name,
                            env_vars=metadata.auth_env_vars
                        )
                    else:
                        safe_log(
                            self.logger,
                            "debug",
                            "Tool authentication valid",
                            tool_name=name
                        )
                except Exception as e:
                    results[name] = False
                    safe_log(
                        self.logger,
                        "error",
                        "Error validating tool auth",
                        tool_name=name,
                        error=str(e)
                    )
            else:
                results[name] = False
                safe_log(
                    self.logger,
                    "warning",
                    "Tool requires auth but has no validate_auth method",
                    tool_name=name
                )

        valid_count = sum(1 for v in results.values() if v)
        safe_log(
            self.logger,
            "info",
            "Auth validation complete",
            total=len(results),
            valid=valid_count,
            invalid=len(results) - valid_count
        )

        return results

    def get_tool_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered tools.

        Returns:
            List of tool info dicts
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": self._metadata[name].category.value,
                "requires_auth": self._metadata[name].requires_auth,
                "cost_estimate": self._metadata[name].cost_estimate,
                "rate_limit": self._metadata[name].rate_limit,
                "version": self._metadata[name].version,
            }
            for name, tool in self._tools.items()
        ]

    def count(self) -> int:
        """Get total number of registered tools."""
        return len(self._tools)

    def clear(self) -> None:
        """Clear all registered tools. Useful for testing."""
        safe_log(
            self.logger,
            "info",
            "Clearing all tools",
            count=len(self._tools)
        )
        self._tools.clear()
        self._metadata.clear()

    def __repr__(self) -> str:
        """String representation of registry."""
        return f"<ToolRegistry tools={len(self._tools)}>"


# Global registry instance - initialized by app
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry.
    Must be initialized via initialize_registry() first.

    Returns:
        Global ToolRegistry instance

    Raises:
        RuntimeError: If registry not initialized
    """
    if _registry is None:
        raise RuntimeError(
            "Tool registry not initialized. "
            "Call initialize_registry() from your app first."
        )
    return _registry


def initialize_registry(logger: Optional[LoggerProtocol] = None) -> ToolRegistry:
    """
    Initialize the global tool registry.
    Should be called once at app startup.

    Args:
        logger: Logger instance to use (Maven Logger or stdlib Logger)

    Returns:
        Initialized registry
    """
    global _registry
    _registry = ToolRegistry(logger=logger)
    return _registry
