import os
import json
from pathlib import Path
from retrieval.models.config import RetrieverConfig

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

class ConfigManager:
    def __init__(self, config_path: Path | None = None):
        retriever_config_path = os.getenv("RETRIEVER_CONFIG_PATH")
        if not retriever_config_path:
            raise Exception("RETRIEVER_CONFIG_PATH not set in environment variables.")
        self.config_path = Path(retriever_config_path)
        self.config = self.load_config()

    def load_config(self) -> RetrieverConfig:
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                config = RetrieverConfig(**json.load(f))
        else:
            config = RetrieverConfig()
        return config

    def save_config(self, config: RetrieverConfig):
        data = {
            "root": config.root,
        }
