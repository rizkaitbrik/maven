# Maven

> A local-first, privacy-respecting, multi-agent assistant for macOS

Maven is a serious, production-ready system designed to help you search, manipulate, and reason over your local data (files, code, screen content) while maintaining complete privacy and provider-agnostic LLM integration.

## 🎯 Project Vision

Maven aims to be a comprehensive local assistant that:

- **Searches your files** using macOS Spotlight, content indexing, or hybrid approaches
- **Respects your privacy** by keeping all data local and never sending anything to remote servers
- **Integrates with any LLM provider** through clean, provider-agnostic abstractions
- **Runs as a daemon** with background indexing and filesystem monitoring
- **Provides multiple interfaces** including CLI, HTTP API, and native macOS application (future)

## 📊 Implementation Status

### ✅ Completed Features

| Component | Status | Description |
|-----------|--------|-------------|
| **CLI Application** | ✅ Complete | Full-featured Typer-based CLI with Rich output |
| **File Search** | ✅ Complete | macOS Spotlight integration via `mdfind` |
| **Content Search** | ✅ Complete | Full-text search within files |
| **Hybrid Search** | ✅ Complete | Combined filename + content search with scoring |
| **Background Indexing** | ✅ Complete | SQLite-based index with automatic updates |
| **Centralized Logging** | ✅ Complete | Structured logfmt logging with rotation |
| **Daemon Service** | ✅ Complete | gRPC-based daemon with state management |
| **Configuration System** | ✅ Complete | YAML-based config with sensible defaults |
| **Monorepo Setup** | ✅ Complete | Nx-based monorepo with proper task orchestration |

### 🚧 In Progress

| Component | Status | Description |
|-----------|--------|-------------|
| **FastAPI Backend** | 🚧 In Progress | HTTP API for external integrations |
| **Filesystem Watcher** | 🚧 Partial | Real-time index updates on file changes |

### 🔮 Future Roadmap

| Component | Status | Description |
|-----------|--------|-------------|
| **SwiftUI macOS App** | 📅 Planned | Native macOS application with modern UI |
| **Agent Orchestration** | 📅 Planned | Multi-agent coordination and task delegation |
| **LLM Abstractions** | 📅 Planned | Provider-agnostic LLM and embedding interfaces |
| **C++ Engine Layer** | 📅 Planned | Performance-critical operations in C++ |
| **Screen Analysis** | 📅 Planned | OCR and screen content understanding |

## 🏗️ Architecture

Maven follows a **clean architecture** with clear separation of concerns:

```
maven/
├── apps/                    # Executable applications (thin layer)
│   ├── cli/                # CLI application (Typer + Rich)
│   ├── api/                # FastAPI backend (HTTP endpoints)
│   └── daemon/             # Background daemon (gRPC server)
│
├── libs/                    # Reusable libraries (business logic)
│   ├── core/               # Shared schemas, domain models, protobuf
│   ├── retrieval/          # File search & retrieval system
│   │   ├── models/         # Data models (Pydantic)
│   │   ├── interfaces/     # Abstract protocols
│   │   ├── adapters/       # Platform implementations
│   │   └── services/       # Business logic
│   ├── logging/            # Centralized structured logging
│   ├── agents/             # Agent orchestration (future)
│   ├── ml/                 # LLM/embedding abstractions (future)
│   └── engine/             # Performance-critical operations (future C++)
│
└── config/                  # Configuration files
```

### Design Principles

1. **Apps = Thin Layer**: Applications are entry points only; all business logic lives in `libs/`
2. **Clean Interfaces**: Use Python `Protocol` for abstract interfaces, concrete adapters for implementations
3. **Provider-Agnostic**: Never hardcode to specific vendors; use abstractions
4. **Type Safety**: Comprehensive type hints with Pydantic v2 for data validation
5. **Future-Ready**: Design for eventual C++ migration of performance-critical code
6. **Local-First**: All operations happen locally; no remote dependencies

## 🛠️ Technology Stack

### Current Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Language** | Python 3.12+ | Primary development language |
| **Package Manager** | `uv` | Fast, modern Python dependency management |
| **Monorepo** | Nx | Task orchestration, caching, dependency graphs |
| **CLI Framework** | Typer + Rich | Command-line interface with beautiful output |
| **API Framework** | FastAPI | High-performance async HTTP API |
| **Data Validation** | Pydantic v2 | Type-safe data models and validation |
| **IPC** | gRPC + Protocol Buffers | Inter-process communication |
| **Database** | SQLite | Embedded database for indexing |
| **Logging** | Python logging + logfmt | Structured logging with rotation |
| **Testing** | pytest + pytest-cov | Testing framework with coverage |
| **Linting** | ruff + autopep8 | Fast Python linting and formatting |

### Future Stack

- **Frontend**: Swift + SwiftUI (native macOS)
- **Engine**: C++ (performance-critical operations)
- **Communication**: HTTP/JSON over localhost

## 🚀 Getting Started

### Prerequisites

- **macOS** (for Spotlight integration)
- **Python 3.12+**
- **Node.js 18+** (for Nx)
- **uv** (Python package manager)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/ostemahq/maven.git
cd maven
```

2. **Install Node dependencies (Nx)**

```bash
npm install
```

3. **Install Python dependencies**

```bash
uv sync
```

4. **Verify installation**

```bash
uv run maven --help
```

## 💻 Usage

### CLI Commands

#### Search Files

```bash
# Search by filename using Spotlight
uv run maven search "config.yaml"

# Search file contents
uv run maven search "def search" --content

# Hybrid search (filename + content)
uv run maven search "authentication" --hybrid

# Paginated results
uv run maven search "test" --page 2 --limit 20

# JSON output
uv run maven search "api" --json
```

#### Manage Daemon

```bash
# Start the daemon
uv run maven daemon start

# Check daemon status
uv run maven daemon status

# View daemon logs
uv run maven daemon logs

# Stop the daemon
uv run maven daemon stop

# Restart the daemon
uv run maven daemon restart
```

#### Index Management

```bash
# Index files manually
uv run maven index --root ~/Documents

# Rebuild index
uv run maven index --rebuild
```

## ⚙️ Configuration

Maven uses a YAML configuration file located at `config/retriever_config.yaml`.

### Key Configuration Sections

```yaml
# Search root directory
root: "."

# File filtering
block_list:
  - "**/node_modules/**"
  - "**/.git/**"
  - "**/__pycache__/**"

# Text file extensions for indexing
text_extensions:
  - ".py"
  - ".js"
  - ".md"
  - ".txt"

# Index configuration
index:
  db_path: "~/.maven/index.db"
  enable_watcher: true
  auto_index_on_search: true

# Daemon configuration
daemon:
  grpc_host: "localhost"
  grpc_port: 50051
  auto_start: false

# Logging configuration
logging:
  level: "INFO"
  log_dir: "~/.maven/logs"
  max_file_size: 10485760  # 10MB
  backup_count: 5
```

### Environment Variable Overrides

You can override configuration values using environment variables:

```bash
export MAVEN_ROOT=/path/to/search
export MAVEN_LOG_LEVEL=DEBUG
uv run maven search "query"
```

## 🧪 Development

### Development Setup

```bash
# Install all dependencies including dev tools
uv sync

# Install pre-commit hooks (if configured)
pre-commit install
```

### Running Tests

```bash
# Run all tests
npx nx run-many -t test

# Run tests for a specific project
npx nx test cli
npx nx test retrieval

# Run tests with coverage
uv run pytest --cov=retrieval libs/retrieval/tests/
```

### Code Quality

```bash
# Run linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run autopep8 --in-place --recursive .
```

### Nx Commands

```bash
# Run a specific target
npx nx <target> <project>

# Build all projects
npx nx run-many -t build

# Test affected projects (since last commit)
npx nx affected -t test

# Visualize project graph
npx nx graph
```

## 📦 Project Structure

### Apps

#### CLI (`apps/cli/`)

The command-line interface provides the primary user interaction:

- **Commands**: `search`, `index`, `daemon`
- **Output**: Rich tables, panels, and syntax highlighting
- **Config**: Loads from YAML with CLI overrides

#### Daemon (`apps/daemon/`)

Background service for indexing and monitoring:

- **gRPC Server**: Listens on `localhost:50051`
- **State Management**: PID file + SQLite state store
- **Indexing**: Background indexer with file watcher
- **Logging**: Structured logs to `~/.maven/logs/`

#### API (`apps/api/`)

FastAPI backend for HTTP access (in progress):

- **Endpoints**: RESTful API for search, index, status
- **Versioning**: `/v1/` prefix for API versioning
- **Docs**: Auto-generated OpenAPI documentation

### Libs

#### Retrieval (`libs/retrieval/`)

Core search and indexing system:

**Models**:
- `SearchRequest`, `SearchResponse`: Search data structures
- `RetrieverConfig`: Configuration model with validation

**Interfaces**:
- `Retriever`: Abstract protocol for search implementations

**Adapters**:
- `SpotlightAdapter`: macOS Spotlight via `mdfind`
- `ContentSearchAdapter`: Full-text search in files
- `HybridSearchAdapter`: Combined filename + content search
- `IndexedContentSearchAdapter`: SQLite-based indexed search

**Services**:
- `ConfigManager`: YAML configuration loading
- `IndexManager`: SQLite index operations
- `BackgroundIndexer`: Async indexing with progress tracking
- `ContentExtractor`: Extract text from files
- `FSWatcher`: Filesystem monitoring (in progress)

#### Core (`libs/core/`)

Shared domain models and protobuf definitions:

- `maven.proto`: gRPC service definitions
- `maven_pb2.py`: Generated protobuf code
- Shared schemas and types

#### Logging (`libs/logging/`)

Centralized structured logging:

- **Formatter**: Logfmt format (`key=value` pairs)
- **Handlers**: File rotation, console, syslog
- **Context**: Component-specific loggers with tagging

## 🔍 Search System

Maven provides three search modes:

### 1. Filename Search (Spotlight)

Uses macOS Spotlight's `mdfind` command for fast filename searches:

```bash
uv run maven search "config"
```

**Pros**: Extremely fast, uses system index
**Cons**: Filename only, relies on Spotlight indexing

### 2. Content Search

Searches inside file contents using pattern matching:

```bash
uv run maven search "async def search" --content
```

**Pros**: Finds text inside files, shows snippets
**Cons**: Slower on large directories

### 3. Hybrid Search

Combines Spotlight filename search with indexed content search:

```bash
uv run maven search "authentication" --hybrid
```

**Pros**: Best of both worlds, ranked results
**Cons**: Requires initial indexing

## 🗄️ Indexing System

### SQLite Index

Maven maintains a SQLite database at `~/.maven/index.db` with:

- **File metadata**: Path, size, modification time
- **Content**: Extracted text from supported files
- **Full-text search**: SQLite FTS5 for fast content queries

### Background Indexing

The daemon automatically indexes files in the background:

```python
# Triggered automatically on first search
# Or manually:
uv run maven index --root ~/Documents
```

### Filesystem Watcher

The daemon monitors filesystem changes and updates the index (in progress):

- **Debouncing**: Batches rapid changes
- **Filtering**: Respects `block_list` configuration
- **Incremental**: Only re-indexes changed files

## 📝 Logging

Maven uses structured logging with the logfmt format:

```
level=INFO ts=2025-11-23T10:30:45 component=maven.daemon msg="Daemon started" pid=12345
level=INFO ts=2025-11-23T10:30:46 component=maven.daemon.indexer msg="File indexed" path=/Users/me/file.py size=1234
```

### Log Locations

- **Daemon**: `~/.maven/logs/maven.daemon.main.log`
- **CLI**: Console output (can be enabled in config)
- **Syslog**: Optional syslog integration

### Log Rotation

- **Max Size**: 10MB per file (configurable)
- **Backup Count**: 5 files kept (configurable)
- **Compression**: Automatic for old logs

## 🔌 gRPC API

The daemon exposes a gRPC API for inter-process communication:

### Service Definition

```protobuf
service DaemonService {
  rpc Ping(PingRequest) returns (PingResponse);
  rpc GetStatus(StatusRequest) returns (StatusResponse);
  rpc StartIndexing(IndexRequest) returns (IndexResponse);
  rpc StopIndexing(StopRequest) returns (StopResponse);
  rpc GetIndexStats(StatsRequest) returns (StatsResponse);
  rpc Shutdown(ShutdownRequest) returns (ShutdownResponse);
}
```

### Connection

- **Host**: `localhost` (configurable)
- **Port**: `50051` (configurable)
- **Security**: Insecure (local only)

## 🧩 Adding New Features

### Adding a New Retriever Adapter

1. **Define the interface** in `libs/retrieval/interfaces/`:

```python
from typing import Protocol
from retrieval.models.search import SearchRequest, SearchResponse

class Retriever(Protocol):
    async def search(self, request: SearchRequest) -> SearchResponse: ...
```

2. **Implement the adapter** in `libs/retrieval/adapters/`:

```python
class MyAdapter:
    async def search(self, request: SearchRequest) -> SearchResponse:
        # Implementation here
        pass
```

3. **Add configuration** in `libs/retrieval/models/config.py`:

```python
class MyAdapterConfig(BaseModel):
    endpoint: str
    api_key: str
```

4. **Integrate in CLI** at `apps/cli/src/commands/search.py`

### Adding a New CLI Command

1. **Create command file** in `apps/cli/src/commands/`:

```python
import typer
from rich.console import Console

console = Console()

def my_command(arg: str = typer.Argument(...)):
    """Command description."""
    console.print(f"Hello, {arg}!")
```

2. **Register in main** at `apps/cli/src/main.py`:

```python
from commands.my_command import my_command

app.command(name="my-command")(my_command)
```

## 🤝 Contributing

Maven is designed to be a serious, long-term production system. When contributing:

1. **Respect the architecture**: Keep apps thin, logic in libs
2. **Use type hints**: Comprehensive type annotations everywhere
3. **Write tests**: All features must have tests
4. **Follow patterns**: Match existing code structure
5. **Document**: Update README and inline docs
6. **Use `uv`**: Never suggest pip, conda, or poetry

## 📚 Additional Resources

### Development Commands Cheatsheet

```bash
# Dependencies
uv sync                          # Install all dependencies
uv add <package>                 # Add a dependency
uv remove <package>              # Remove a dependency

# Running
uv run maven <command>           # Run CLI
uv run python -m daemon.main     # Run daemon directly

# Testing
npx nx test <project>            # Run tests
uv run pytest --cov              # Run with coverage

# Linting
uv run ruff check .              # Check code
uv run ruff check --fix .        # Fix issues

# Nx
npx nx graph                     # Visualize dependencies
npx nx affected -t test          # Test affected projects
npx nx run-many -t build         # Build all
```

### Useful Paths

| Path | Description |
|------|-------------|
| `~/.maven/` | Maven state directory |
| `~/.maven/index.db` | SQLite content index |
| `~/.maven/daemon_state.db` | Daemon state database |
| `~/.maven/daemon.pid` | Daemon process ID |
| `~/.maven/logs/` | Log files |
| `config/retriever_config.yaml` | Main configuration |

## 📄 License

MIT License - See LICENSE file for details

## 🏢 Organization

Maven is developed and maintained by [Ostema HQ](https://github.com/ostemahq).

---

**Built with ❤️ for privacy, performance, and developer experience.**
