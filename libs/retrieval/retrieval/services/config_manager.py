import os
import json
from pathlib import Path
from retrieval.models.config import RetrieverConfig

try:
    import yaml
except ImportError:
    yaml = None

try:
    from dotenv import load_dotenv, find_dotenv
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
            with open(self.config_path, "r") as f:
                if self.config_path.suffix in [".yaml", ".yml"] and yaml:
                    config_data = yaml.safe_load(f) or {}
                else:
                    config_data = json.load(f)
        
        # Merge environment-based allowed list with config file
        if self.env_allowed_list:
            file_allowed_list = config_data.get("allowed_list", [])
            config_data["allowed_list"] = list(set(self.env_allowed_list + file_allowed_list))
        
        return RetrieverConfig(**config_data) if config_data else RetrieverConfig()

    def save_config(self, config: RetrieverConfig):
        data = {
            "root": str(config.root),
            "index_path": str(config.index_path),
            "allowed_list": config.allowed_list,
            "block_list": config.block_list,
            "text_extensions": config.text_extensions,
        }
        
        with open(self.config_path, "w") as f:
            if self.config_path.suffix in [".yaml", ".yml"] and yaml:
                yaml.safe_dump(data, f, default_flow_style=False)
            else:
                json.dump(data, f, indent=2)
