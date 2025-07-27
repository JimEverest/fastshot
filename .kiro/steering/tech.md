# Technology Stack & Build System

## Core Technologies
- **Language**: Python 3.7+
- **GUI Framework**: Tkinter with CustomTkinter for modern UI components
- **Image Processing**: Pillow (PIL) for image manipulation
- **Screen Capture**: mss, pyautogui, screeninfo for multi-monitor support
- **Input Handling**: pynput for global hotkeys and mouse/keyboard events
- **OCR Engine**: PaddleOCR with PaddlePaddle backend (local processing)
- **AI Integration**: OpenAI API with httpx for HTTP requests
- **Cloud Storage**: boto3 for AWS S3 integration with encryption
- **Configuration**: configparser for INI-based settings
- **Packaging**: setuptools with PyInstaller for distribution

## Key Dependencies
```
pyautogui, pynput, screeninfo, mss
Pillow, pyperclip, pywin32
paddlepaddle, paddleocr
customtkinter, flask
openai>=1.0.0, httpx>=0.24.0
boto3>=1.26.0, botocore>=1.29.0
configparser, minio
psutil                          # Memory usage monitoring and optimization
threading, queue                # Async operations and background processing
hashlib                         # Cache integrity validation with checksums
fcntl/msvcrt                   # Cross-platform file locking for cache synchronization
```

## Build & Development Commands

### Installation
```bash
pip install -r requirements.txt
pip install fastshot  # From PyPI
```

### Development Setup
```bash
git clone https://github.com/jimeverest/fastshot.git
cd fastshot
pip install -r requirements.txt
```

### Running
```bash
fastshot                    # Installed package
python -m fastshot.main     # Development
python run.py              # Alternative entry point
```

### Testing
```bash
pytest tests/                           # Run test suite
python test_final_integration.py       # Cloud sync optimization integration tests
python test_performance_optimization.py # Performance and memory usage tests
python test_backward_compatibility.py  # Backward compatibility verification
```

### Building Distribution
```bash
python setup.py sdist bdist_wheel  # Python package
build.bat                          # PyInstaller executable (Windows)
```

## Configuration System
- **Config File**: `fastshot/config.ini` (INI format)
- **User Config**: Auto-created on first run with defaults
- **Sections**: Shortcuts, ScreenPen, CloudSync, PowerGenAI, Paths
- **Environment Variables**: Support for OpenAI API keys and endpoints

## Cloud Sync Optimization Features

### Performance Architecture
- **Two-Tier Metadata System**: Lightweight metadata indexes separate from full session files
- **Intelligent Local Caching**: File-based cache with integrity validation and cross-process locking
- **Smart Synchronization**: Filename-based comparison leveraging immutable session nature
- **Asynchronous Operations**: Non-blocking background operations with progress tracking

### Technical Implementation
- **MetaCacheManager**: Local metadata caching with SHA256 integrity validation
- **AsyncOperationManager**: Background operation management with thread pool and progress callbacks
- **Enhanced CloudSyncManager**: Metadata operations with atomic updates and rollback mechanisms
- **Optimized UI**: Fast-loading session manager with progressive updates

### Performance Achievements
- **UI Loading**: Reduced from 3-5 minutes to <2 seconds (99%+ improvement)
- **Memory Efficiency**: <80MB baseline usage with <0.1MB growth for large datasets
- **Network Optimization**: >95% reduction in initial bandwidth usage
- **Backward Compatibility**: 100% compatibility with existing sessions and workflows

### Error Handling & Recovery
- **Cache Corruption Recovery**: Automatic detection and repair with cloud rebuild capability
- **Network Resilience**: Graceful degradation with offline mode support
- **Atomic Operations**: Rollback mechanisms for failed operations
- **Comprehensive Validation**: Checksum verification and integrity monitoring