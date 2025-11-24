import json
import os
from pathlib import Path

from retrieval.models.config import (
    DaemonConfig,
    HybridSearchConfig,
    IndexConfig,
    LoggingConfig,
    RetrieverConfig,
)

try:
    import yaml
except ImportError:
    yaml = None

try:
    from dotenv import find_dotenv, load_dotenv
    # Try to find and load .env file from current directory or parents
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        # Fallback: try loading from current directory
        load_dotenv()
except Exception:
    pass


class ConfigManager:
    def __init__(self, config_path: Path | None = None):
        retriever_config_path = os.getenv("RETRIEVER_CONFIG_PATH")
        if not retriever_config_path:
            # Default to config/retriever_config.yaml in project root
            retriever_config_path = "config/retriever_config.yaml"
        
        self.config_path = Path(retriever_config_path)
        
        # Load environment-based allowed list
        self.env_allowed_list = self._load_env_allowed_list()
        
        self.config = self.load_config()

    def _load_env_allowed_list(self) -> list[str]:
        """Load allowed list from environment variables."""
        allowed_list_str = os.getenv("RETRIEVER_ALLOWED_LIST", "")
        if allowed_list_str:
            # Support comma-separated paths
            return [p.strip() for p in allowed_list_str.split(",") if p.strip()]
        return []

    def load_config(self) -> RetrieverConfig:
        config_data = {}
        
        if self.config_path.exists():
            with open(self.config_path) as f:
                if self.config_path.suffix in [".yaml", ".yml"] and yaml:
                    config_data = yaml.safe_load(f) or {}
                else:
                    config_data = json.load(f)
        
        # Merge environment-based allowed list with config file
        if self.env_allowed_list:
            file_allowed_list = config_data.get("allowed_list", [])
            combined = list(set(self.env_allowed_list + file_allowed_list))
            config_data["allowed_list"] = combined
        
        # Parse nested configurations
        if "index" in config_data and isinstance(config_data["index"], dict):
            config_data["index"] = IndexConfig(**config_data["index"])
        
        if "hybrid_search" in config_data and isinstance(
            config_data["hybrid_search"], dict
        ):
            config_data["hybrid_search"] = HybridSearchConfig(
                **config_data["hybrid_search"]
            )
        
        if "logging" in config_data and isinstance(config_data["logging"], dict):
            config_data["logging"] = LoggingConfig(**config_data["logging"])
        
        if "daemon" in config_data and isinstance(config_data["daemon"], dict):
            config_data["daemon"] = DaemonConfig(**config_data["daemon"])
        
        return RetrieverConfig(**config_data) if config_data else RetrieverConfig()

    def save_config(self, config: RetrieverConfig):
        data = {
            "root": str(config.root),
            "index_path": str(config.index_path),
            "allowed_list": config.allowed_list,
            "block_list": config.block_list,
            "text_extensions": config.text_extensions,
            "index": {
                "db_path": config.index.db_path,
                "enable_watcher": config.index.enable_watcher,
                "debounce_ms": config.index.debounce_ms,
                "max_file_size": config.index.max_file_size,
                "auto_index_on_search": config.index.auto_index_on_search,
                "reindex_on_startup": config.index.reindex_on_startup,
            },
            "hybrid_search": {
                "enabled": config.hybrid_search.enabled,
                "filename_match_weight": config.hybrid_search.filename_match_weight,
                "content_match_weight": config.hybrid_search.content_match_weight,
                "deduplicate": config.hybrid_search.deduplicate,
            },
        }
        
        with open(self.config_path, "w") as f:
            if self.config_path.suffix in [".yaml", ".yml"] and yaml:
                yaml.safe_dump(data, f, default_flow_style=False)
            else:
                json.dump(data, f, indent=2)
