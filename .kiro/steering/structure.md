# Project Structure & Organization

## Root Directory Layout
```
fastshot/                   # Main package directory
├── main.py                # Application entry point and main class
├── config.ini             # Default configuration file
├── _config_reset.ini      # Reset configuration template
├── __init__.py            # Package initialization
│
├── Core Modules
├── snipping_tool.py       # Screenshot capture functionality
├── image_window.py        # Floating image window management
├── screen_pen.py          # System-wide screen annotation
├── window_control.py      # Window management and hotkey handling
├── ask_dialog.py          # AI assistant dialog interface
│
├── Session & Sync
├── session_manager.py     # Session save/load functionality
├── session_manager_ui.py  # Optimized session management UI with fast loading
├── cloud_sync.py          # Enhanced AWS S3 cloud synchronization with metadata operations
├── meta_cache.py          # Local metadata caching and synchronization system
├── async_operations.py    # Background operation management with progress tracking
│
├── UI Components
├── enhanced_save_dialog.py # Enhanced file save dialogs
├── paint_tool.py          # Drawing and annotation tools
├── text_tool.py           # Text annotation functionality
│
├── Plugins
├── plugins/               # Plugin directory
├── plugin_ocr.py          # OCR plugin implementation
├── plugin_ask.py          # AI assistant plugin
│
├── Resources & Utils
├── resources/             # Static resources (models, assets)
├── utils/                 # Utility modules
├── settings/              # Settings management
├── decoded/               # Decoded/processed files
├── recordings/            # Screen recordings
└── __pycache__/           # Python cache files
```

## Key Architecture Patterns

### Main Application Class
- **SnipasteApp**: Central application controller in `main.py`
- Manages all subsystems (snipping, windows, plugins, sync)
- Handles global hotkeys and configuration

### Window Management
- **ImageWindow**: Individual floating screenshot windows
- **VisibilityIndicator**: Shows count of hidden windows
- Always-on-top and transparency control

### Plugin Architecture
- Plugin discovery in `plugins/` directory
- Standard interface: `get_plugin_info()` and `run(app_context)`
- Hotkey registration and activation system

### Configuration Management
- INI-based configuration with sections
- Auto-generation of default config on first run
- Runtime config reloading support

## File Naming Conventions
- Snake_case for Python modules
- Descriptive names indicating functionality
- Plugin prefix for plugin modules (`plugin_*.py`)
- UI suffix for user interface modules (`*_ui.py`)

## Import Structure
- Relative imports within package
- Conditional imports for optional features
- Plugin system uses dynamic imports with `importlib`

## Data Flow
1. **Input**: Global hotkeys → HotkeyListener → SnipasteApp
2. **Capture**: SnippingTool → PIL Image → ImageWindow
3. **Processing**: OCR/AI plugins → Results display
4. **Storage**: SessionManager → Local files + CloudSync → S3
5. **Optimized Cloud Sync Flow**:
   - **UI Loading**: MetaCacheManager → Cached metadata → Instant display
   - **Background Sync**: AsyncOperationManager → Smart sync → Progressive updates
   - **Session Save**: CloudSync → Metadata index creation → Atomic updates
   - **Cache Management**: Integrity validation → Recovery mechanisms → User feedback

## Cloud Sync Optimization Architecture

### Performance-Optimized Components
- **MetaCacheManager**: Local metadata caching with file locking and integrity validation
- **AsyncOperationManager**: Background operations with progress tracking and cancellation
- **Enhanced CloudSyncManager**: Metadata operations with rollback and error recovery
- **Optimized SessionManagerUI**: Fast loading with progressive updates and cache management

### Cache Directory Structure
```
~/.fastshot/
├── sessions/                    # Full session files cache
├── meta_cache/
│   ├── meta_indexes/           # Individual lightweight metadata files
│   ├── overall_meta.json       # Master metadata file
│   └── cache_info.json         # Cache state and validation info
└── cache_lock                  # Cross-process synchronization
```

### Cloud Storage Structure
```
S3 Bucket:
├── sessions/                   # Full session files (existing)
├── meta_indexes/              # Lightweight metadata indexes (new)
└── overall_meta.json          # Master metadata file (new)
```