# Conductor

An extensible, event-driven plugin kernel for composing local services and application capabilities.

## Overview

Conductor provides a minimal runtime with dynamic plugin discovery, lifecycle management, commands, events, permissions, HTTP APIs and React plugin pages.

## Getting Started

### Prerequisites

- Python 3.11 or 3.12
- Node.js 18+ and Yarn
- [Poetry](https://python-poetry.org/docs/#installation)

### Installation

```bash
poetry install
python scripts/sync_plugin_dependencies.py --ecosystem all --install
cd WebApp && yarn install
```

### Running the System

```bash
poetry run python -m conductor
```

The backend listens on `127.0.0.1:5678` by default. Start it before the WebApp so
the generated plugin route manifest is available, then run `yarn start` from
`WebApp/`. The fixed core pages are `/core/plugin-management` and `/core/terminal`.

## Documentation

Comprehensive documentation can be found in the `docs/source` directory, covering:
- Plugin Development
- Event System
- Command Trees
- Docker Deployment

The project-wide design and development rules are in [`guideline.md`](guideline.md).

For a current code-oriented inventory of the runtime, plugins, data flow, gaps, and
cleanup candidates, see [`docs/project_audit.md`](docs/project_audit.md).

## License

MIT
