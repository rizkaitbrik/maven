from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from agents.models.config import MemoryConfig


@contextmanager
def create_checkpointer(config: MemoryConfig | None = None) -> Iterator[BaseCheckpointSaver | None]:
    """Factory to create a checkpointer for agent memory.

    Args:
        config: Memory configuration

    Yields:
        Checkpointer instance or None if disabled
    """
    config = config or MemoryConfig()

    if not config.enabled:
        yield None
        return

    match config.backend:
        case "memory":
            yield MemorySaver()

        case "sqlite":
            from langgraph.checkpoint.sqlite import SqliteSaver
            db_path = Path(config.db_path).expanduser()
            db_path.parent.mkdir(parents=True, exist_ok=True)

            with SqliteSaver.from_conn_string(str(db_path)) as checkpointer:
                yield checkpointer

        case "redis":
            from langgraph.checkpoint.redis import RedisSaver
            redis_uri = f"redis://{config.redis_host or 'localhost'}:{config.redis_port or 6379}/{config.redis_db or 0}"

            with RedisSaver.from_conn_string(redis_uri) as checkpointer:
                yield checkpointer

        case _:
            raise ValueError(f"Unknown checkpointer backend: {config.backend}")