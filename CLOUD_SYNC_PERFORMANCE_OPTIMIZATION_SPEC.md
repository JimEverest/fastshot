# Cloud Sync Performance Optimization Spec

## Problem Statement

The current cloud session management system has significant performance issues:

1. **Slow UI Loading**: SessionManagerUI startup requires downloading ALL cloud sessions (37 files, several MB to tens of MB each) to display the Cloud Sessions tab, taking several minutes.

2. **No Caching System**: Every UI load downloads complete session files from cloud, even when only metadata is needed for display.

3. **No Meta Index System**: No lightweight metadata files exist to provide quick session information without downloading full sessions.

4. **Blocking UI**: All downloads happen synchronously, blocking the user interface.

## Requirements

### Core Requirements

1. **Meta Index System**: Create lightweight metadata files for each session containing only display information (name, description, tags, color, class, image count, creation date) - excluding heavy data like thumbnails and full session content.

2. **Overall Meta File**: Maintain a master metadata file containing basic information about all sessions for quick cache comparison and initial loading.

3. **Local Caching**: Implement local cache for both metadata and full session files, with intelligent cache invalidation based on filename (since sessions are only created/deleted, not updated).

4. **Asynchronous Operations**: All cloud operations (save, load, sync) should be asynchronous and non-blocking to the UI.

5. **Rebuild Functionality**: Provide "Rebuild All Indexes" button for initial setup when no cache exists or when cloud has no meta indexes.

### Update Points

1. **On Session Save**: Update both the session's meta index file and the overall meta file.
2. **Rebuild Overall List**: Button to download all meta indexes from cloud and rebuild the overall meta file.
3. **Rebuild All Indexes**: Button to download all sessions, generate meta indexes, and create overall meta file.

### UI Integration Requirements

1. **Progressive Loading**: Load cached metadata first, then asynchronously update with fresh data.
2. **Visual Feedback**: Show loading indicators and progress for background operations.
3. **Error Handling**: Graceful degradation when cloud operations fail.
4. **Hotkey Integration**: Maintain Shift+F6 hotkey functionality for testing.

## Design

### File Structure

```
Cloud Storage (S3):
├── sessions/
│   ├── 20250621114615_tt1.fastshot          # Full session files
│   ├── 20250621121205_tt3.fastshot
│   └── ...
├── meta_indexes/
│   ├── 20250621114615_tt1.meta.json         # Individual metadata files
│   ├── 20250621121205_tt3.meta.json
│   └── ...
└── overall_meta.json                        # Master metadata file

Local Cache:
~/.fastshot/
├── sessions/                                # Full session files cache
├── meta_cache/
│   ├── meta_indexes/                        # Individual metadata cache
│   └── overall_meta.json                    # Master metadata cache
└── cache_info.json                          # Cache state information
```

### Meta Index File Format

```json
{
  "filename": "20250621114615_tt1.fastshot",
  "name": "Test Session 1",
  "desc": "Sample session for testing",
  "tags": ["test", "demo"],
  "color": "blue",
  "class": "development",
  "image_count": 3,
  "created_at": "2025-06-21T11:46:15",
  "file_size": 2048576,
  "checksum": "abc123def456"
}
```

### Overall Meta File Format

```json
{
  "last_updated": "2025-01-27T10:30:00",
  "total_sessions": 37,
  "sessions": [
    {
      "filename": "20250621114615_tt1.fastshot",
      "created_at": "2025-06-21T11:46:15",
      "file_size": 2048576,
      "checksum": "abc123def456"
    }
  ]
}
```

## Implementation Tasks

### Task 1: Create Meta Index Infrastructure
**Scope**: Core metadata handling system
**Files**: `fastshot/cloud_sync.py`, `fastshot/meta_cache.py` (new)

- Create `MetaCacheManager` class to handle local metadata caching
- Add methods to `CloudSyncManager` for meta index operations:
  - `save_meta_index(filename, metadata)`
  - `load_meta_index(filename)`
  - `list_meta_indexes()`
- Implement local cache directory structure
- Add cache validation and cleanup methods

### Task 2: Update Session Save Process
**Scope**: Modify session saving to create meta indexes
**Files**: `fastshot/cloud_sync.py`, `fastshot/session_manager.py`

- Modify `save_session_to_cloud()` to create and upload meta index file
- Update overall meta file when saving new sessions
- Ensure atomic operations (rollback on failure)
- Add progress callbacks for UI feedback

### Task 3: Implement Overall Meta File Management
**Scope**: Master metadata file operations
**Files**: `fastshot/cloud_sync.py`, `fastshot/meta_cache.py`

- Add `update_overall_meta()` method
- Implement `rebuild_overall_meta()` for full reconstruction
- Add cache comparison logic for incremental updates
- Handle concurrent access and file locking

### Task 4: Optimize SessionManagerUI Loading
**Scope**: Make UI loading fast and responsive
**Files**: `fastshot/session_manager_ui.py`

- Modify `_load_cloud_sessions_with_metadata()` to use cached meta indexes
- Implement progressive loading (cache first, then async updates)
- Add loading indicators and progress bars
- Remove the current 10-session limit for metadata loading

### Task 5: Add Rebuild Functionality
**Scope**: UI buttons for cache management
**Files**: `fastshot/session_manager_ui.py`

- Add "Rebuild All Indexes" button to Cloud Sessions tab
- Add "Rebuild Overall List" button
- Implement progress dialogs for long-running operations
- Add error handling and user feedback

### Task 6: Implement Asynchronous Operations
**Scope**: Make all cloud operations non-blocking
**Files**: `fastshot/cloud_sync.py`, `fastshot/session_manager_ui.py`

- Convert all cloud operations to async/threading
- Add operation queuing system
- Implement progress callbacks and cancellation
- Update UI components to handle async results

### Task 7: Add Cache Management UI
**Scope**: User controls for cache operations
**Files**: `fastshot/session_manager_ui.py`

- Add cache status display (size, last updated)
- Add "Clear Cache" functionality
- Add cache validation and repair options
- Integrate with existing Settings tab

### Task 8: Testing and Integration
**Scope**: End-to-end testing and optimization
**Files**: All modified files

- Test with existing 37-session cloud setup
- Verify Shift+F6 hotkey functionality
- Performance benchmarking (startup time, memory usage)
- Error scenario testing (network failures, corrupted cache)

## Success Criteria

1. **Fast Startup**: SessionManagerUI Cloud Sessions tab loads in <2 seconds with cached data
2. **Progressive Updates**: Fresh metadata loads asynchronously without blocking UI
3. **Reduced Bandwidth**: Only download full sessions when explicitly requested by user
4. **Reliable Caching**: Cache invalidation works correctly, no stale data issues
5. **User Experience**: Clear feedback for all operations, graceful error handling
6. **Backward Compatibility**: Existing sessions continue to work without migration

## Phase 2 Enhancements (Future)

- Thumbnail caching and lazy loading
- Compression for meta index files
- Batch operations for multiple sessions
- Conflict resolution for concurrent modifications
- Advanced filtering and search capabilities
- Export/import functionality for metadata

## Risk Mitigation

1. **Data Loss**: Implement atomic operations and rollback mechanisms
2. **Cache Corruption**: Add checksum validation and auto-repair
3. **Network Issues**: Implement retry logic and offline mode
4. **Performance Regression**: Benchmark against current implementation
5. **User Confusion**: Provide clear status indicators and help text

## Testing Strategy

1. **Unit Tests**: Core caching and metadata operations
2. **Integration Tests**: Full save/load/sync workflows
3. **Performance Tests**: Startup time, memory usage, network efficiency
4. **User Acceptance**: Test with real 37-session dataset
5. **Error Scenarios**: Network failures, corrupted files, permission issues