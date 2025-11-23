````markdown
# Maven Daemon Service & Centralized Logging

## 1. Overview

This document describes the architecture and implementation plan for the **Maven Daemon Service** and **centralized logging** system in a local-first, CLI-driven environment.

Goals:

- A **standalone daemon** (`apps/daemon/`) running as a background process
- **gRPC** communication between `apps/cli` and `apps/daemon`
- **File system monitoring** with automatic index updates
- **Index persistence** via SQLite
- **Centralized structured logging** using **logfmt**
- **Dual persistence** for daemon state:
  - PID file for process management
  - SQLite DB for runtime state & index metadata
- Logs written to:
  - Rotating log files in `~/.maven/logs/`
  - Syslog / journald

The daemon follows a **clean architecture / ports & adapters** design:

- `core/` → domain logic & ports (no framework dependencies)
- `infrastructure/` → gRPC server, filesystem watcher, SQLite index, etc.
- `app.py` → composition root (dependency injection)
- `main.py` → entry point used by `maven-daemon` executable

---

## 2. High-Level Architecture

```text
┌───────────────┐
│  CLI (apps/cli)│
│  - Typer/Click │
│  - gRPC client │
└───────┬───────┘
        │ gRPC
        ▼
┌────────────────────────────────────┐
│ Daemon (apps/daemon)              │
│  - gRPC Server (infrastructure)   │
│  - Daemon Orchestrator (core)     │
│  - File System Watcher            │
│  - Index Manager (SQLite)         │
│  - Background Indexer             │
└──────────────┬────────────────────┘
               │
        ┌──────▼───────┐
        │ SQLite Index │
        │ ~/.maven/db  │
        └──────────────┘

┌──────────────────────────────────┐
│ Logging (libs/logging)           │
│  - logfmt formatter              │
│  - Rotating file handler         │
│  - Syslog handler                │
│  - Context & component tagging   │
└──────────────┬───────────────────┘
               │
        ┌──────▼──────────────────┐
        │ Logs                     │
        │  ~/.maven/logs/*.log     │
        │  + syslog/journald       │
        └──────────────────────────┘
````

---

## 3. Monorepo Layout

```text
apps/
├── daemon/              # Daemon process
│   ├── pyproject.toml
│   ├── project.json     # Nx project config (if using Nx)
│   └── src/
│       ├── app.py       # Composition root (wiring)
│       ├── config.py    # Settings / env
│       ├── main.py      # Entry point (maven-daemon)
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── ports.py
│       │   ├── services.py    # MavenDaemon, IndexManager, etc.
│       │   └── state.py       # DaemonStateManager (PID + logical state)
│       └── infrastructure/
│           ├── __init__.py
│           ├── grpc/
│           │   ├── server.py  # gRPC server setup
│           │   └── service.py # gRPC service impl (adapts to core)
│           ├── fs/
│           │   └── watcher.py # FileSystemWatcher
│           ├── index/
│           │   └── sqlite_index.py  # SQLite index implementation
│           └── state/
│               └── sqlite_state.py  # SQLite daemon state impl
│
└── cli/
    ├── pyproject.toml
    └── src/
        └── commands/
            └── daemon.py      # CLI commands: start/stop/status/logs

libs/
├── logging/
│   ├── pyproject.toml
│   └── logging_lib/
│       ├── __init__.py
│       ├── logger.py       # Public logger API (get_logger)
│       ├── formatters.py   # LogfmtFormatter
│       └── handlers.py     # File/syslog handlers
└── core/
    ├── pyproject.toml
    └── proto/
        ├── maven.proto     # gRPC definitions
        ├── maven_pb2.py
        └── maven_pb2_grpc.py
```

Notes:

* **No `project_name` folder under `src/`**, as requested.
* `apps/daemon/src/core/` and `apps/daemon/src/infrastructure/` follow **ports & adapters**.

---

## 4. Centralized Logging (libs/logging)

### 4.1 Package Layout

```text
libs/logging/
├── pyproject.toml
└── logging_lib/
    ├── __init__.py        # exposes get_logger()
    ├── logger.py          # MavenLogger / get_logger
    ├── formatters.py      # LogfmtFormatter
    └── handlers.py        # file & syslog handlers
```

### 4.2 Logfmt Formatter

```python
# libs/logging/logging_lib/formatters.py
import logging
from datetime import datetime

_RESERVED_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process"
}

class LogfmtFormatter(logging.Formatter):
    """Logfmt formatter: level=INFO ts=... component=... msg="message" key=value"""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).isoformat()
        parts = [
            f"level={record.levelname}",
            f"ts={ts}",
            f"component={record.name}",
            f'msg="{record.getMessage().replace("\"", "\\\"")}"',
        ]

        # Attach custom attributes as key=value
        for key, value in record.__dict__.items():
            if key in _RESERVED_KEYS:
                continue
            parts.append(f"{key}={value}")

        return " ".join(parts)
```

### 4.3 Logger Setup

```python
# libs/logging/logging_lib/logger.py
import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from .formatters import LogfmtFormatter

DEFAULT_LOG_DIR = Path.home() / ".maven" / "logs"

class MavenLogger:
    def __init__(
        self,
        name: str,
        log_dir: Optional[Path] = None,
        level: str = "INFO",
        enable_syslog: bool = True,
        enable_console: bool = False,
        max_file_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.propagate = False

        if self.logger.handlers:
            # Already configured (avoid duplicates)
            return

        log_dir = log_dir or DEFAULT_LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        formatter = LogfmtFormatter()

        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "maven-daemon.log",
            maxBytes=max_file_size,
            backupCount=backup_count,
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Syslog handler (optional)
        if enable_syslog:
            try:
                sys_handler = logging.handlers.SysLogHandler(address="/dev/log")
                sys_handler.setFormatter(formatter)
                self.logger.addHandler(sys_handler)
            except OSError:
                # Syslog not available (e.g. macOS without /dev/log): ignore
                pass

        # Console handler (optional)
        if enable_console:
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self.logger.addHandler(console)


def get_logger(component: str) -> logging.Logger:
    """Public entrypoint for other packages."""
    # You can centralize log settings from config here later.
    logger = MavenLogger(f"maven.{component}").logger
    return logger
```

### 4.4 Example Log Output

```text
level=INFO ts=2025-01-01T12:00:00 component=maven.daemon msg="Daemon started" pid=12345
level=INFO ts=2025-01-01T12:00:01 component=maven.daemon.watcher msg="File changed" path=/home/user/file.py action=modified
level=INFO ts=2025-01-01T12:00:02 component=maven.daemon.indexer msg="File indexed" path=/home/user/file.py size=1234
level=ERROR ts=2025-01-01T12:00:03 component=maven.cli.search msg="Search failed" error="connection refused"
```

---

## 5. gRPC Protocol (libs/core/proto)

### 5.1 `maven.proto`

```protobuf
syntax = "proto3";

package maven;

service DaemonService {
  // Health
  rpc Ping (PingRequest) returns (PingResponse);

  // Daemon status
  rpc GetStatus (StatusRequest) returns (StatusResponse);

  // Index control
  rpc StartIndexing (IndexRequest) returns (IndexResponse);
  rpc StopIndexing (StopRequest) returns (StopResponse);

  // Index stats
  rpc GetIndexStats (StatsRequest) returns (StatsResponse);

  // Shutdown daemon
  rpc Shutdown (ShutdownRequest) returns (ShutdownResponse);
}

message PingRequest {}
message PingResponse {
  bool alive = 1;
  string version = 2;
}

message StatusRequest {}
message StatusResponse {
  bool running = 1;
  bool indexing = 2;
  bool watcher_active = 3;
  int32 files_indexed = 4;
  string uptime = 5;
}

message IndexRequest {
  string root_path = 1;
  bool rebuild = 2;
}

message IndexResponse {
  bool started = 1;
  string message = 2;
}

message StopRequest {}
message StopResponse {
  bool stopped = 1;
  string message = 2;
}

message StatsRequest {}
message StatsResponse {
  int32 files_indexed = 1;
  int64 total_bytes = 2;
  string last_indexed_at = 3;
}

message ShutdownRequest {}
message ShutdownResponse {
  bool ok = 1;
}
```

### 5.2 Code Generation

```bash
python -m grpc_tools.protoc \
  -I libs/core/proto \
  --python_out=libs/core/proto \
  --grpc_python_out=libs/core/proto \
  libs/core/proto/maven.proto
```

Generated files:

* `libs/core/proto/maven_pb2.py`
* `libs/core/proto/maven_pb2_grpc.py`

---

## 6. Daemon Application (apps/daemon)

### 6.1 Core Layer

#### 6.1.1 Ports

```python
# apps/daemon/src/core/ports.py
from typing import Protocol, Sequence
from pathlib import Path
from datetime import datetime

class IndexRepository(Protocol):
    def index_file(self, path: Path) -> None: ...
    def remove_file(self, path: Path) -> None: ...
    def get_stats(self) -> dict: ...

class StateStore(Protocol):
    def load(self) -> dict: ...
    def save(self, data: dict) -> None: ...

class FileWatcher(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...

class Clock(Protocol):
    def now(self) -> datetime: ...
```

#### 6.1.2 Daemon State Manager

```python
# apps/daemon/src/core/state.py
import os
from pathlib import Path
import psutil

from libs.logging.logging_lib import get_logger

class DaemonStateManager:
    """PID + high level daemon flags/state (in memory + persisted store)."""

    def __init__(self, state_dir: Path | None = None):
        self.state_dir = state_dir or (Path.home() / ".maven")
        self.pid_file = self.state_dir / "daemon.pid"
        self.logger = get_logger("daemon.state")

    def is_running(self) -> bool:
        if not self.pid_file.exists():
            return False
        try:
            pid = int(self.pid_file.read_text())
        except ValueError:
            return False
        return psutil.pid_exists(pid)

    def write_pid(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        pid = os.getpid()
        self.pid_file.write_text(str(pid))
        self.logger.info("PID file written", pid=pid)

    def clear_pid(self) -> None:
        if self.pid_file.exists():
            self.pid_file.unlink()
            self.logger.info("PID file removed")
```

#### 6.1.3 Daemon Service (Orchestrator)

```python
# apps/daemon/src/core/services.py
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .ports import IndexRepository, FileWatcher, StateStore, Clock
from .state import DaemonStateManager
from libs.logging.logging_lib import get_logger

@dataclass
class DaemonStatus:
    running: bool
    indexing: bool
    watcher_active: bool
    files_indexed: int
    uptime: str

@dataclass
class MavenDaemon:
    index_repo: IndexRepository
    watcher: FileWatcher
    state_store: StateStore
    clock: Clock
    state_manager: DaemonStateManager
    started_at: datetime | None = field(default=None)

    def __post_init__(self):
        self.logger = get_logger("daemon")

    def start(self):
        if self.state_manager.is_running():
            raise RuntimeError("Daemon already running")
        self.state_manager.write_pid()
        self.started_at = self.clock.now()
        self.watcher.start()
        self._set_state(indexing=False)
        self.logger.info("Daemon started")

    def shutdown(self):
        self.watcher.stop()
        self._set_state(indexing=False)
        self.state_manager.clear_pid()
        self.logger.info("Daemon stopped")

    def start_indexing(self, root: Path, rebuild: bool = False):
        self.logger.info("Start indexing requested", root=str(root), rebuild=rebuild)
        # Implementation: queue a background task / mark state
        self._set_state(indexing=True)

    def stop_indexing(self):
        self.logger.info("Stop indexing requested")
        self._set_state(indexing=False)

    def get_status(self) -> DaemonStatus:
        stats = self.index_repo.get_stats()
        uptime = "unknown"
        if self.started_at:
            delta = self.clock.now() - self.started_at
            uptime = str(delta).split(".")[0]  # simple string
        return DaemonStatus(
            running=self.state_manager.is_running(),
            indexing=self._get_state().get("indexing", False),
            watcher_active=True,  # from watcher in a more complete impl
            files_indexed=stats.get("files_indexed", 0),
            uptime=uptime,
        )

    def _set_state(self, **kwargs):
        data = self._get_state()
        data.update(kwargs)
        self.state_store.save(data)

    def _get_state(self) -> dict:
        return self.state_store.load() or {}
```

### 6.2 Infrastructure Layer

#### 6.2.1 SQLite Index

```python
# apps/daemon/src/infrastructure/index/sqlite_index.py
import sqlite3
from pathlib import Path
from typing import Dict

from libs.logging.logging_lib import get_logger
from core.ports import IndexRepository  # adjust import path as needed

class SQLiteIndexRepository(IndexRepository):
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = get_logger("daemon.index")
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    size INTEGER,
                    mtime REAL
                )
            """)
            conn.commit()

    def index_file(self, path: Path) -> None:
        st = path.stat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "REPLACE INTO files (path, size, mtime) VALUES (?, ?, ?)",
                (str(path), st.st_size, st.st_mtime),
            )
            conn.commit()
        self.logger.info("File indexed", path=str(path), size=st.st_size)

    def remove_file(self, path: Path) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM files WHERE path = ?", (str(path),))
            conn.commit()
        self.logger.info("File removed from index", path=str(path))

    def get_stats(self) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM files")
            count, total_bytes = cur.fetchone()
        return {"files_indexed": count, "total_bytes": total_bytes}
```

#### 6.2.2 SQLite State Store

```python
# apps/daemon/src/infrastructure/state/sqlite_state.py
import sqlite3
from pathlib import Path
from typing import Dict

from core.ports import StateStore
from libs.logging.logging_lib import get_logger

class SQLiteStateStore(StateStore):
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = get_logger("daemon.state_store")
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daemon_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def load(self) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM daemon_state")
            data = {k: (v == "true" if v in ("true", "false") else v) for k, v in cur}
        return data

    def save(self, data: Dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM daemon_state")
            conn.executemany(
                "INSERT INTO daemon_state (key, value) VALUES (?, ?)",
                [(k, str(v).lower() if isinstance(v, bool) else str(v)) for k, v in data.items()],
            )
            conn.commit()
        self.logger.info("Daemon state saved", keys=list(data.keys()))
```

#### 6.2.3 File System Watcher

(Implementation can use `watchdog`, conceptual sketch below):

```python
# apps/daemon/src/infrastructure/fs/watcher.py
from threading import Thread
from pathlib import Path
from typing import Callable

from libs.logging.logging_lib import get_logger
from core.ports import FileWatcher

class SimpleFileWatcher(FileWatcher):
    def __init__(self, root: Path, on_change: Callable[[Path, str], None]):
        self.root = root
        self.on_change = on_change
        self.logger = get_logger("daemon.watcher")
        self._thread: Thread | None = None
        self._stop = False

    def start(self) -> None:
        # TODO: replace with watchdog; this is a placeholder
        self.logger.info("Starting file watcher", root=str(self.root))
        # self._thread = Thread(target=self._loop, daemon=True)
        # self._thread.start()

    def stop(self) -> None:
        self._stop = True
        self.logger.info("Stopping file watcher")

    # def _loop(self):
    #   ...
```

### 6.3 gRPC Server

```python
# apps/daemon/src/infrastructure/grpc/server.py
from concurrent import futures
import grpc

from libs.logging.logging_lib import get_logger
from core.services import MavenDaemon
from libs.core.proto import maven_pb2, maven_pb2_grpc  # adjust path

class DaemonServiceImpl(maven_pb2_grpc.DaemonServiceServicer):
    def __init__(self, daemon: MavenDaemon):
        self.daemon = daemon
        self.logger = get_logger("daemon.grpc")

    def Ping(self, request, context):
        status = self.daemon.get_status()
        return maven_pb2.PingResponse(
            alive=status.running,
            version="0.1.0",
        )

    def GetStatus(self, request, context):
        s = self.daemon.get_status()
        return maven_pb2.StatusResponse(
            running=s.running,
            indexing=s.indexing,
            watcher_active=s.watcher_active,
            files_indexed=s.files_indexed,
            uptime=s.uptime,
        )

    def StartIndexing(self, request, context):
        self.daemon.start_indexing(root=Path(request.root_path), rebuild=request.rebuild)
        return maven_pb2.IndexResponse(started=True, message="Indexing started")

    def StopIndexing(self, request, context):
        self.daemon.stop_indexing()
        return maven_pb2.StopResponse(stopped=True, message="Indexing stopped")

    def Shutdown(self, request, context):
        self.daemon.shutdown()
        return maven_pb2.ShutdownResponse(ok=True)


def create_grpc_server(daemon: MavenDaemon, host: str, port: int) -> grpc.Server:
    logger = get_logger("daemon.grpc")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    maven_pb2_grpc.add_DaemonServiceServicer_to_server(
        DaemonServiceImpl(daemon), server
    )
    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    logger.info("gRPC server created", addr=listen_addr)
    return server
```

---

## 7. Composition Root (app.py) & Entry Point (main.py)

### 7.1 app.py

```python
# apps/daemon/src/app.py
from pathlib import Path
from datetime import datetime

from core.services import MavenDaemon
from core.state import DaemonStateManager
from core.ports import Clock
from infrastructure.index.sqlite_index import SQLiteIndexRepository
from infrastructure.state.sqlite_state import SQLiteStateStore
from infrastructure.fs.watcher import SimpleFileWatcher
from infrastructure.grpc.server import create_grpc_server
from libs.logging.logging_lib import get_logger

class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now()

def build_daemon():
    state_dir = Path.home() / ".maven"
    db_path = state_dir / "daemon_state.db"
    index_db_path = state_dir / "daemon_index.db"
    root_path = Path.home()  # could be config-driven

    index_repo = SQLiteIndexRepository(index_db_path)
    state_store = SQLiteStateStore(db_path)
    state_manager = DaemonStateManager(state_dir=state_dir)
    clock = SystemClock()

    def on_change(path: Path, action: str):
        # In a real impl, dispatch to index_repo
        pass

    watcher = SimpleFileWatcher(root=root_path, on_change=on_change)

    daemon = MavenDaemon(
        index_repo=index_repo,
        watcher=watcher,
        state_store=state_store,
        clock=clock,
        state_manager=state_manager,
    )
    return daemon

def build_app(host: str = "127.0.0.1", port: int = 50051):
    daemon = build_daemon()
    server = create_grpc_server(daemon, host=host, port=port)
    return daemon, server
```

### 7.2 main.py

```python
# apps/daemon/src/main.py
import signal
import sys
from libs.logging.logging_lib import get_logger
from app import build_app  # relative imports depending on PYTHONPATH

def main():
    logger = get_logger("daemon.main")
    daemon, server = build_app()
    daemon.start()

    def handle_sigterm(signum, frame):
        logger.info("SIGTERM received, shutting down")
        daemon.shutdown()
        server.stop(grace=None)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    server.start()
    logger.info("Daemon gRPC server started")
    server.wait_for_termination()

if __name__ == "__main__":
    main()
```

---

## 8. CLI Integration (apps/cli)

```python
# apps/cli/src/commands/daemon.py
import subprocess
import sys
from pathlib import Path

import typer
import grpc

from libs.core.proto import maven_pb2, maven_pb2_grpc
from libs.logging.logging_lib import get_logger

app = typer.Typer()
logger = get_logger("cli.daemon")

DAEMON_HOST = "127.0.0.1"
DAEMON_PORT = 50051

def get_client():
    channel = grpc.insecure_channel(f"{DAEMON_HOST}:{DAEMON_PORT}")
    return maven_pb2_grpc.DaemonServiceStub(channel)

@app.command()
def start(detach: bool = typer.Option(True, help="Run as background process")):
    """Start the Maven daemon."""
    try:
        client = get_client()
        resp = client.Ping(maven_pb2.PingRequest())
        if resp.alive:
            typer.echo("✓ Daemon already running")
            return
    except Exception:
        pass

    if detach:
        # Spawn daemon as a subprocess
        # Adjust command to your environment (uv, poetry, etc.)
        subprocess.Popen(
            [sys.executable, "-m", "apps.daemon.src.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        typer.echo("✓ Daemon started (detached)")
    else:
        subprocess.call([sys.executable, "-m", "apps.daemon.src.main"])

@app.command()
def stop():
    """Stop the Maven daemon."""
    client = get_client()
    client.Shutdown(maven_pb2.ShutdownRequest())
    typer.echo("✓ Daemon shutdown signal sent")

@app.command()
def status():
    """Check daemon status."""
    client = get_client()
    resp = client.GetStatus(maven_pb2.StatusRequest())
    if not resp.running:
        typer.echo("✗ Daemon not running")
        return
    typer.echo(f"✓ Daemon running")
    typer.echo(f"  Indexing:      {resp.indexing}")
    typer.echo(f"  Watcher active:{resp.watcher_active}")
    typer.echo(f"  Files indexed: {resp.files_indexed}")
    typer.echo(f"  Uptime:        {resp.uptime}")

@app.command()
def logs(follow: bool = typer.Option(False), lines: int = typer.Option(50)):
    """View daemon logs (simple tail)."""
    log_file = Path.home() / ".maven" / "logs" / "maven-daemon.log"
    if not log_file.exists():
        typer.echo("No log file found")
        raise typer.Exit(1)
    # For now, naive implementation:
    content = log_file.read_text().splitlines()
    for line in content[-lines:]:
        typer.echo(line)
    if follow:
        typer.echo("\n-- follow not yet implemented in this stub --")
```

---

## 9. Configuration

Example `maven_config.yaml` (or reuse your existing config file):

```yaml
daemon:
  grpc_host: 127.0.0.1
  grpc_port: 50051
  state_dir: ~/.maven
  auto_start: false

logging:
  level: INFO
  log_dir: ~/.maven/logs
  max_file_size: 10485760  # 10MB
  backup_count: 5
  enable_syslog: true
  enable_console: false
  components:
    daemon: INFO
    cli: INFO
    indexer: DEBUG
```

---

## 10. pyproject.toml Snippets

### 10.1 `apps/daemon/pyproject.toml`

```toml
[project]
name = "maven-daemon"
version = "0.1.0"
dependencies = [
    "grpcio>=1.60.0",
    "grpcio-tools>=1.60.0",
    "psutil>=5.9.0",
    "watchdog>=4.0.0",       # for real fs watcher (future)
    "logging-lib",           # libs/logging
]

[project.scripts]
maven-daemon = "main:main"
```

### 10.2 `libs/logging/pyproject.toml`

```toml
[project]
name = "logging-lib"
version = "0.1.0"
dependencies = []
```

---

## 11. CLI Usage Examples

```bash
# Start daemon
maven daemon start

# Check status
maven daemon status
# ✓ Daemon running
#   Indexing:      False
#   Watcher active:True
#   Files indexed: 1247
#   Uptime:        2:34:12

# Stop daemon
maven daemon stop

# View last 50 log lines
maven daemon logs --lines 50

# Start and use search (daemon keeps index live)
maven search "function" --hybrid
```

---

## 12. Future Enhancements

* Proper **filesystem watcher** using `watchdog` with event → index pipeline
* **Background indexer** with job queue & backoff
* **systemd / launchd** integration for auto-start on boot
* **Metrics endpoint** (Prometheus) in the daemon
* Remote daemon support (non-localhost)
* Secure gRPC (mTLS) for remote scenarios

This Markdown reflects the requested daemon architecture with:

* Proper **daemon directory structure**
* **Design patterns** (clean architecture, ports & adapters)
* **gRPC** between CLI and daemon
* **Centralized, structured logging** across all components.
