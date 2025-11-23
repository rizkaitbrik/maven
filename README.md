# Maven

A Python CLI tool for searching files using platform-native indexing (macOS Spotlight).

## Overview

Maven provides a fast, configurable search interface that leverages macOS Spotlight's indexing capabilities through `mdfind`. Built as an Nx monorepo with a modular architecture, Maven supports flexible path filtering, pagination, and multiple output formats.

## Features

- 🔍 **Fast Search** - Leverages macOS Spotlight indexing via `mdfind`
- 📝 **Content Search** - Search inside file contents with regex support
- 🎯 **Configurable Filtering** - Allow/block specific paths and patterns
- 📄 **Pagination Support** - Browse results across pages
- 🎨 **Rich CLI Output** - Beautiful tables and snippets with Rich library
- 📊 **JSON Output** - Machine-readable format for scripting
- 🏗️ **Modular Architecture** - Clean separation of concerns with adapters and interfaces

## Project Structure

```
maven/
├── apps/
│   ├── api/          # API application
│   └── cli/          # CLI application (main entry point)
├── libs/
│   ├── core/         # Core shared library
│   └── retrieval/    # Retrieval library
│       ├── adapters/     # Platform adapters (SpotlightAdapter)
│       ├── interfaces/   # Protocol definitions (Retriever)
│       ├── models/       # Data models (config, search)
│       └── services/     # Business logic (config_manager)
└── config/           # Configuration files
```

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
# Install dependencies
uv sync

# Install the CLI
uv pip install -e apps/cli
```

## Usage

### Basic Search

```bash
# Search filenames (Spotlight)
maven search "your query"

# Search file contents
maven search "your query" --content
```

### Advanced Options

```bash
# Search with custom root directory
maven search "query" --root /path/to/directory

# Content search with regex patterns
maven search "def.*\(" --content

# Limit results and pagination
maven search "query" --limit 20 --page 2

# JSON output for scripting
maven search "query" --json

# Combine options
maven search "TODO" --content --root ~/projects --limit 5 --json
```

### Configuration

Create a `config/retriever_config.yaml` file to configure path filtering and content search:

```yaml
root: /Users/username/Documents

# Path filtering
allowed_list:
  - /Users/username/Documents/projects
  - /Users/username/Documents/notes
blocked_list:
  - "**/node_modules/**"
  - "**/.git/**"
  - "**/__pycache__/**"

# Content search - file extensions to treat as text
text_extensions:
  - .py
  - .js
  - .md
  - .txt
  - .json
  # ... add more as needed
```

## Development

This is an Nx monorepo. Common commands:

### Run Tasks

```bash
# Run tests for a specific project
npx nx test cli

# Run tests for all projects
npx nx run-many -t test

# Build a specific project
npx nx build cli

# Lint/format with ruff
npx nx lint retrieval
```

### Testing

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Run tests for specific project
cd libs/retrieval && uv run pytest
```

### Project Graph

Visualize the project dependencies:

```bash
npx nx graph
```

## Architecture

### Retrieval System

The retrieval system follows a clean architecture pattern:

1. **Interfaces** (`retrieval.interfaces.retriever.Retriever`) - Protocol defining the search contract
2. **Adapters** (`retrieval.adapters.spotlight.SpotlightAdapter`) - Platform-specific implementations
3. **Models** - Data structures for requests, responses, and configuration
4. **Services** - Business logic for configuration management

This design allows easy extension with additional search backends (e.g., Elasticsearch, local indexing) by implementing the `Retriever` protocol.

### Configuration Management

The `ConfigManager` service loads configuration from:
1. Config files (`config/retriever_config.yaml`)
2. Environment variables
3. Default values

Configuration supports:
- Root search directory
- Allowed path patterns (glob support)
- Blocked path patterns (glob support)
- Text file extensions for content search

## Requirements

- macOS (uses Spotlight/mdfind)
- Python 3.12+
- Node.js (for Nx)

## Tech Stack

- **Package Management**: uv
- **Monorepo**: Nx
- **CLI Framework**: Typer
- **UI/Formatting**: Rich
- **Testing**: pytest, pytest-cov, pytest-sugar
- **Linting/Formatting**: ruff, autopep8

## Nx Workspace

This workspace uses Nx for task orchestration and caching:

### Useful Nx Commands

```bash
# See affected projects
npx nx affected:graph

# Run tasks on affected projects only
npx nx affected -t test

# Clear cache
npx nx reset

# Sync TypeScript project references
npx nx sync
```

### Nx Console

For a better developer experience, install [Nx Console](https://nx.dev/getting-started/editor-setup) for your IDE.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests: `npx nx run-many -t test`
4. Run linting: `npx nx run-many -t lint`
5. Submit a pull request

## Learn More

- [Nx Documentation](https://nx.dev)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Typer Documentation](https://typer.tiangolo.com)
- [Rich Documentation](https://rich.readthedocs.io)

## License

[Add your license here]
