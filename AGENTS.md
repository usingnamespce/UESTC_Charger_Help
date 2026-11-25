# Repository Guidelines

## Project Structure & Module Organization

- `charge_history/` is the application core. `charge_history_backend.py` samples charger data, stores SQLite history, serves JSON APIs, and hosts the web UI. `charger_api.py` wraps the upstream charger service; `export_locations.py` refreshes map coordinates.
- `charge_history/web/` contains the single-page mobile UI. Treat `web/vendor/leaflet/` as vendored code; edit it only when intentionally upgrading Leaflet.
- `charge_history/*.json` contains tracked station IDs, locations, and coordinate overrides. Keep generated databases out of version control.
- `deploy/` contains the Ubuntu/systemd deployment script, service unit, requirements, and Caddy example.
- Root launchers (`start_server.bat`, `start_server.command`) provide local Windows and macOS startup paths.

## Build, Test, and Development Commands

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python charge_history/charge_history_backend.py --host 127.0.0.1
```

The service is then available at `http://127.0.0.1:8765/`. Use `--host 0.0.0.0` only when LAN access is required.

```bash
python charge_history/export_locations.py   # refresh station_locations.json
python -m compileall charge_history         # syntax-check Python files
curl http://127.0.0.1:8765/api/health       # verify the running service
```

Production deployment is Ubuntu/Debian-specific: `sudo bash deploy/deploy.sh`.

## Coding Style & Naming Conventions

Use four-space indentation and standard Python naming: `snake_case` for functions and variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Keep imports grouped as standard library, third-party, then local modules. Preserve UTF-8 Chinese user-facing text and comments. In `web/index.html`, follow the existing two-space CSS/JavaScript indentation and reuse the established CSS custom properties instead of introducing duplicate colors or spacing values.

## Testing Guidelines

There is currently no automated test suite or coverage threshold. Before submitting changes, run `compileall`, start the backend, check `/api/health`, and exercise every affected API or UI flow. For frontend changes, verify both list and map views at a mobile viewport. New isolated Python logic should include `unittest` tests under `tests/` named `test_*.py`.

## Commit & Pull Request Guidelines

Follow `GIT_WORKFLOW.md`: use a short, one-line commit subject that states what changed, for example `修复地图站点筛选`. Keep commits focused. Pull requests should include a concise summary, affected paths, verification commands/results, and screenshots for visible UI changes. Link relevant issues when available.

## Security & Configuration

Never commit API tokens, passwords, private keys, `/etc/charger-monitor.env`, or `*.db*` files. Use placeholders such as `YOUR_TOKEN_HERE`. Treat upstream API calls as external dependencies and avoid tests or scripts that unintentionally generate excessive requests.
