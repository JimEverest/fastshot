# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fastshot is a GenAI-powered desktop screenshot application for Windows. It provides hotkey-driven screenshot capture, annotation, AI analysis, local OCR, and encrypted AWS S3 cloud sync.

**Version**: 1.5.3
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
pytest tests/                              # Run standard test suite
pytest tests/test_cloud_sync_metadata.py   # Run specific test file
pytest test_plugins/                       # Run plugin tests

# Build package
python -m build

# Build Windows executable
build.bat                                  # Uses PyInstaller

# Install package locally
python setup.py develop
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
| `image_window_gallery.py` | Fullscreen thumbnail grid view with multi-select capabilities |
| `screen_pen.py` | System-wide transparent drawing overlay |
| `window_control.py` | Global hotkey registration and window management |
| `ask_dialog.py` | AI assistant dialog (CustomTkinter) |
| `gpt4o.py` | OpenAI/LLM integration with token exchange |
| `plugin_ocr.py` | RapidOCR (PP-OCRv5) local text extraction |
| `session_manager.py` | Save/load screenshot collections with metadata |
| `cloud_sync.py` | AWS S3 sync with AES-256 encryption |
| `meta_cache.py` | Lightweight metadata caching for fast UI |
| `async_operations.py` | Background thread pool for non-blocking ops |

### Image Window Gallery (`image_window_gallery.py`)

**Components:**
- `ThumbnailButton` - tk.Frame-based thumbnail with checkbox overlay for selection
- `ImageWindowGallery` - Fullscreen gallery view (tk.Toplevel) with scrollable grid

**Features:**
- Grid layout (4 columns) of all current session Image Windows
- Click to toggle selection, double-click to focus original window
- Toolbar: Select All, Deselect All, Invert, Export Selected, Close Selected, Save Selected
- ESC to close, F5 to refresh
- Shortcut: `Shift+F8`

### Plugin System
Plugins live in `fastshot/plugins/` and must implement:
```python
def get_plugin_info():
    return {'name': str, 'id': str, 'default_shortcut': str, 'press_times': int, ...}

def run(app_context):
    pass
```
Plugins are auto-discovered on startup.

**Plugin Utilities** (`fastshot/plugins/utils/`):
- `error_handler.py` - Plugin error handling decorator
- `cloud_error_handler.py` - Cloud operation error handling
- `clipboard_validator.py` - Clipboard content validation
- `hyder.py` - File encryption/decryption utilities
- `last_upload_tracker.py` - Track last cloud upload metadata
- `proxy_header_fix.py` - Proxy/SSL header fixes for cloud requests

### Configuration
- **File**: `fastshot/config.ini` (INI format)
- **Sections**: `[Shortcuts]`, `[ScreenPen]`, `[GenAI]`, `[PowerGenAI]`, `[CloudSync]`
- **Override**: Environment variables take precedence over config file

## Key Hotkeys (Default)

**Screenshot & Annotation:**
- `Shift+A+S` - Screenshot
- `Ctrl+P` - Paint mode
- `Ctrl+T` - Text annotation
- `Ctrl+Z` / `Ctrl+Y` - Undo / Redo

**Screen Pen:**
- `Ctrl+Cmd+Alt` - Toggle screen pen
- `Esc` - Exit screen pen
- `Ctrl+Esc` - Clear pen and hide

**Window Control:**
- `Shift+F1` - Toggle visibility of all image windows
- `Shift+F2` - Load image from file
- `Shift+F3` - Reposition all windows to origin
- `Esc+` ` ` - Always on top ON
- `Cmd+Shift+\` - Always on top OFF
- `Left+Right+Down` / `Left+Right+Up` - Opacity down/up

**Session & Cloud:**
- `Shift+F4` - Save session
- `Shift+F5` - Load session
- `Shift+F6` - Session manager UI
- `Shift+F7` - Quick Notes
- `Shift+F8` - Image Gallery (fullscreen thumbnail view with selection)
- `Shift+F12` - Recover from temp cache

**AI Assistant:**
- `Ctrl` (4x in 1s) - AI assistant dialog

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

### Quick Cloud Modules
- **Quick Cloud Hyder** (`plugin_quick_c_hyder.py`): Encrypt files/folders and upload to S3
  - Activation: Ctrl+Alt alternately 8 times
  - Reads file paths from clipboard
- **Quick Cloud Retriver** (`plugin_quick_c_retriver.py`): Download and decrypt last uploaded file
  - Activation: Ctrl+Win alternately 8 times
  - Auto-opens output folder

### Quick Notes
- **UI**: `fastshot/quick_notes_ui.py` - Tree view for cloud notes
- **Manager**: `fastshot/notes_manager.py` - Note CRUD operations
- **Cache**: `fastshot/notes_cache.py` - Local cache for fast access
- Shortcut: Shift+F7

## File Locations
- **Config**: `fastshot/config.ini`
- **Plugins**: `fastshot/plugins/`
- **Plugin Utils**: `fastshot/plugins/utils/`
- **Settings UI**: `fastshot/settings/`
- **Resources**: `fastshot/resources/`
- **Tests**: `tests/`, `test_plugins/`, `test_root/`
- **Workflow**: `.github/workflows/python-publish.yml` (PyPI publish on release)
- **Entry Points**: `run.py` (dev), `fastshot/main.py` (module), `setup.py` (build)

## Package Build
- `setup.py` defines package metadata and dependencies
- `pyproject.toml` specifies setuptools build backend
- Windows executable built via `build.bat` using PyInstaller

## CI/CD
GitHub Actions (`.github/workflows/python-publish.yml`) publishes to PyPI on release tag creation.
