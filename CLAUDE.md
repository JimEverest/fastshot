# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fastshot is a GenAI-powered desktop screenshot application for Windows. It provides hotkey-driven screenshot capture, annotation, AI analysis, local OCR, and encrypted AWS S3 cloud sync.

**Version**: 1.5.2
**Entry Point**: `fastshot/main.py` → `SnipasteApp` class

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python run.py
# or
python -m fastshot.main
# or (after pip install)
fastshot

# Run tests
pytest tests/
pytest test_plugins/

# Build package
python -m build

# Build Windows executable
build.bat
```

## Architecture Overview

### Core Application Flow
1. `SnipasteApp` (main.py) initializes DPI awareness, loads config, starts global hotkey listener
2. `HotkeyListener` (window_control.py) captures keyboard events via `pynput`
3. Hotkeys trigger: screenshot capture, annotation tools, AI dialog, plugin execution
4. `SnippingTool` creates overlay for region selection → `ImageWindow` displays floating result
5. Sessions saved via `SessionManager` → synced to S3 via `CloudSyncManager`

### Key Subsystems

| Module | Purpose |
|--------|---------|
| `snipping_tool.py` | Multi-monitor screenshot capture with overlay selection |
| `image_window.py` | Floating window with zoom/drag/opacity control |
| `screen_pen.py` | System-wide transparent drawing overlay |
| `window_control.py` | Global hotkey registration and window management |
| `ask_dialog.py` | AI assistant dialog (CustomTkinter) |
| `gpt4o.py` | OpenAI/LLM integration with token exchange |
| `plugin_ocr.py` | RapidOCR (PP-OCRv5) local text extraction |
| `session_manager.py` | Save/load screenshot collections with metadata |
| `cloud_sync.py` | AWS S3 sync with AES-256 encryption |
| `meta_cache.py` | Lightweight metadata caching for fast UI |
| `async_operations.py` | Background thread pool for non-blocking ops |

### Plugin System
Plugins live in `fastshot/plugins/` and must implement:
```python
def get_plugin_info():
    return {'name': str, 'id': str, 'default_shortcut': str, 'press_times': int, ...}

def run(app_context):
    pass
```
Plugins are auto-discovered on startup.

### Configuration
- **File**: `fastshot/config.ini` (INI format)
- **Sections**: `[Shortcuts]`, `[ScreenPen]`, `[GenAI]`, `[PowerGenAI]`, `[CloudSync]`
- **Override**: Environment variables take precedence over config file

## Key Hotkeys (Default)
- `Shift+A+S` - Screenshot
- `Ctrl+P` - Paint mode
- `Ctrl+T` - Text annotation
- `Ctrl+Cmd+Alt` - Screen pen toggle
- `Ctrl` (4x in 1s) - AI assistant
- `Shift+F4` - Save session
- `Shift+F5` - Load session
- `Shift+F6` - Session manager UI

## Cloud Sync Architecture
The cloud sync uses a two-tier metadata system for performance:
1. **Lightweight meta indexes** - Stored separately from full session data
2. **MetaCacheManager** - SHA256 validation, cross-process file locking
3. **AsyncOperationManager** - 3-thread worker pool for background operations

Performance: UI loads in <2 seconds (previously 3-5 minutes).

## Important Patterns

### Async Operations
All cloud/heavy operations use `AsyncOperationManager` with callbacks:
```python
self.async_manager.submit_task(task_func, callback=on_complete)
```

### Error Handling
- `plugins/utils/cloud_error_handler.py` - Cloud operation errors
- `plugins/utils/error_handler.py` - Plugin errors
- Automatic cache corruption recovery in `meta_cache.py`

### Security
- Local OCR (no cloud processing for text extraction)
- AES-256 encryption for cloud storage
- Encrypted files disguised as PNG images
- Credentials cleaned from logs

## File Locations
- **Config**: `fastshot/config.ini`
- **Plugins**: `fastshot/plugins/`
- **Settings UI**: `fastshot/settings/`
- **Resources**: `fastshot/resources/`
- **Tests**: `tests/`, `test_plugins/`, `test_root/`

## CI/CD
GitHub Actions (`.github/workflows/python-publish.yml`) publishes to PyPI on release tag creation.
