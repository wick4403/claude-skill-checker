# Claude Skill Checker

A portable, browser-based dashboard that gives you a categorized overview of all Claude Code skills and agents installed on your computer.

![Claude Skill Checker screenshot](https://img.shields.io/badge/Python-3.8+-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)

## Features

- **Categorized overview** of all installed Claude skills and agents
- **Startup check** — detects new or removed skills since your last session
- **Refresh button** — updates the list without reloading the page
- **Smart cache** — only re-reads files that actually changed (fast refreshes)
- **Diff notifications** — shows which skills were added or removed
- **Search** — filter by name or description
- **"Nieuw" badge** — highlights newly added skills in the current session
- **Portable** — works on any PC with Python installed, no configuration needed

## Categories

Skills are automatically grouped by prefix:

| Category | Prefix |
|---|---|
| GSD – Project Management | `gsd-` |
| SEO | `seo-`, `seo` |
| Development & Engineering | `agent-`, `code-`, `hook-`, `mcp-`, `plugin-`, `test-`, `skill-`, and more |
| Agents | Files in `~/.claude/agents/` |
| Overig / Utilities | Everything else |

## Requirements

- Python 3.8 or higher
- Claude Code installed (skills located in `~/.claude/skills/`)
- No `pip install` needed — uses Python standard library only

## Usage

### Windows
Double-click `Start Skills Overview.bat`

The app automatically:
1. Stops any previous instance on port 8765
2. Starts the server
3. Opens your browser to `http://127.0.0.1:8765`

### Any OS (Mac / Linux / Windows)
```bash
python skills_overview.py
```

The browser opens automatically. Press `Ctrl+C` in the terminal to stop.

## How it works

```
~/.claude/skills/*/SKILL.md   ← reads YAML frontmatter (name, description)
~/.claude/agents/*.md         ← reads agent definitions
        ↓
skills_overview.py            ← Python HTTP server (stdlib only)
  ├── scan_all()              ← incremental scan using mtime cache
  ├── /                       ← serves embedded HTML dashboard
  └── /api/skills             ← returns JSON with categorized items
        ↓
Browser                       ← renders cards, handles search & refresh
```

### Cache
On first run, all skill files are read and cached in `~/.claude/.skills_overview_cache.json`. On subsequent runs and refreshes, only files with a changed modification time are re-read — the rest are served from cache instantly.

### Portability
The app detects `~/.claude` automatically using `pathlib.Path.home()`. Copy `skills_overview.py` (and optionally the `.bat` file) to any user's machine and run it — no configuration needed.

## Files

| File | Description |
|---|---|
| `skills_overview.py` | Main application (server + embedded UI) |
| `Start Skills Overview.bat` | Windows launcher — double-click to start |

## License

MIT
