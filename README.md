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
`WebApp/` (the frontend is available at `http://127.0.0.1:8678`). The fixed core
pages are `/core/plugin-management` and `/core/terminal`.

### Mobile Demo Apps

The iOS and Android entry points use the shared Tauri 2 app in `MobileApp/`.
Install the JavaScript dependencies once:

```bash
cd MobileApp && npm install
```

Start the demo from the platform entry directory:

```bash
cd iosapp && npm run dev
cd androidapp && npm run dev
```

The app accepts a server IP or URL, username, and password. A bare IP uses
`http://<ip>:8678` by default, so the mobile device must be able to reach the
Conductor WebApp and backend proxy on that address. To build a debug iOS
simulator app or Android APK, run `npm run build` from `iosapp/` or `androidapp/`
respectively. iOS builds require Xcode; Android builds require Android Studio,
the Android SDK/NDK, and the Rust Android targets.

## Documentation

Comprehensive documentation can be found in the `docs/source` directory, covering:
- Plugin Development
- Event System
- Command Trees
- Docker Deployment
- Core Plugin Management
- Mobile Demo Apps

The project-wide design and development rules are in [`guideline.md`](guideline.md).

For a current code-oriented inventory of the runtime, plugins, data flow, gaps, and
cleanup candidates, see [`docs/project_audit.md`](docs/project_audit.md).

## License

MIT
