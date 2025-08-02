"""
NotesCacheManager - Manages local caching for Cloud Quick Notes.

This module provides single-layer caching functionality for notes metadata
to improve UI loading performance by avoiding the need to download full notes
just to display basic information in the notes list.
"""

import json
import os
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging

# Platform-specific imports for file locking
try:
    import fcntl  # Unix/Linux
    HAS_FCNTL = True
except ImportError:
    import msvcrt  # Windows
    HAS_FCNTL = False

logger = logging.getLogger(__name__)


class NotesCacheManager:
    """Manages local caching for Cloud Quick Notes with single-layer index caching."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize NotesCacheManager with cache directory.
        
        Args:
            cache_dir: Optional custom cache directory. If None, uses default ~/.fastshot/quicknotes/
        """
        if cache_dir is None:
            # Use default cache directory in user home
            home_dir = Path.home()
            self.cache_dir = home_dir / ".fastshot" / "quicknotes"
        else:
            self.cache_dir = Path(cache_dir)
        
        # Cache files
        self.overall_notes_index_file = self.cache_dir / "overall_notes_index.json"
        self.cache_info_file = self.cache_dir / "cache_info.json"
        self.cache_lock_file = self.cache_dir / "cache_lock"
        
        # Ensure directories exist
        self._create_cache_directories()
        
        # Initialize cache info if it doesn't exist
        self._initialize_cache_info()
    
    def _create_cache_directories(self):
        """Create cache directory structure if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Notes cache directory created at {self.cache_dir}")
        except Exception as e:
            logger.error(f"Failed to create notes cache directories: {e}")
            raise
    
    def _initialize_cache_info(self):
        """Initialize cache info file with default values if it doesn't exist."""
        if not self.cache_info_file.exists():
            cache_info = {
                "version": "1.0",
                "last_sync": None,
                "cache_size_bytes": 0,
                "total_notes": 0,
                "integrity_check": {
                    "last_validated": None,
                    "status": "unknown",
                    "checksum": None
                }
            }
            self._save_cache_info(cache_info)
    
    def _acquire_lock(self) -> bool:
        """
        Acquire file lock for concurrent access protection.
        
        Returns:
            bool: True if lock acquired successfully, False otherwise
        """
        try:
            # Create lock file if it doesn't exist
            self.cache_lock_file.touch()
            
            # Open lock file and acquire exclusive lock
            self._lock_fd = open(self.cache_lock_file, 'w')
            
            if HAS_FCNTL:
                # Unix/Linux file locking
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                # Windows file locking - use a simpler approach for testing
                try:
                    msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as e:
                    # If locking fails, continue without lock for testing
                    logger.warning(f"Windows file locking failed, continuing without lock: {e}")
            
            # Write process info to lock file if file is still open
            if not self._lock_fd.closed:
                self._lock_fd.write(f"pid:{os.getpid()}\ntime:{datetime.now().isoformat()}\n")
                self._lock_fd.flush()
            
            logger.debug("Notes cache lock acquired")
            return True
        except (IOError, OSError) as e:
            logger.warning(f"Failed to acquire notes cache lock: {e}")
            if hasattr(self, '_lock_fd') and self._lock_fd and not self._lock_fd.closed:
                try:
                    self._lock_fd.close()
                except:
                    pass
            return False
    
    def _release_lock(self):
        """Release file lock."""
        try:
            if hasattr(self, '_lock_fd') and self._lock_fd and not self._lock_fd.closed:
                if HAS_FCNTL:
                    # Unix/Linux file unlocking
                    try:
                        fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass  # File might already be unlocked
                else:
                    # Windows file unlocking - unlock before closing
                    try:
                        msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass  # File might already be unlocked
                
                self._lock_fd.close()
                self._lock_fd = None
                logger.debug("Notes cache lock released")
        except Exception as e:
            logger.warning(f"Error releasing notes cache lock: {e}")
            # Ensure file handle is closed even if unlocking fails
            if hasattr(self, '_lock_fd') and self._lock_fd:
                try:
                    if not self._lock_fd.closed:
                        self._lock_fd.close()
                    self._lock_fd = None
                except:
                    pass
    
    def _load_cache_info(self) -> Dict[str, Any]:
        """Load cache info from file."""
        try:
            if self.cache_info_file.exists():
                with open(self.cache_info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load notes cache info: {e}")
        
        # Return default cache info if loading fails
        return {
            "version": "1.0",
            "last_sync": None,
            "cache_size_bytes": 0,
            "total_notes": 0,
            "integrity_check": {
                "last_validated": None,
                "status": "unknown",
                "checksum": None
            }
        }
    
    def _save_cache_info(self, cache_info: Dict[str, Any]):
        """Save cache info to file."""
        try:
            with open(self.cache_info_file, 'w', encoding='utf-8') as f:
                json.dump(cache_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save notes cache info: {e}")
            raise
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return f"sha256:{sha256_hash.hexdigest()}"
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    def _calculate_cache_size(self) -> int:
        """Calculate total size of cache directory in bytes."""
        total_size = 0
        try:
            for root, dirs, files in os.walk(self.cache_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.exists():
                        total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to calculate notes cache size: {e}")
        return total_size
    
    def get_cached_index(self) -> Dict:
        """
        Get cached notes index from local cache.
        
        Returns:
            Dict: Cached notes index dictionary, or empty structure if not found
        """
        if not self._acquire_lock():
            logger.warning("Could not acquire lock for reading cached notes index")
            return self._get_empty_index()
        
        try:
            if self.overall_notes_index_file.exists():
                with open(self.overall_notes_index_file, 'r', encoding='utf-8') as f:
                    cached_index = json.load(f)
                
                logger.info(f"Loaded cached notes index with {len(cached_index.get('notes', []))} notes")
                return cached_index
            else:
                logger.info("No cached notes index found, returning empty index")
                return self._get_empty_index()
                
        except Exception as e:
            logger.error(f"Failed to load cached notes index: {e}")
            return self._get_empty_index()
        finally:
            self._release_lock()
    
    def _get_empty_index(self) -> Dict:
        """Get empty notes index structure."""
        return {
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_notes": 0,
            "notes": [],
            "statistics": {
                "total_words": 0,
                "total_size_bytes": 0,
                "most_recent_update": None
            }
        }
    
    def update_cache_index(self, index_data: Dict) -> None:
        """
        Update local cache with new notes index data.
        
        Args:
            index_data: Notes index dictionary to cache
        """
        if not self._acquire_lock():
            logger.error("Could not acquire lock for cache index update")
            return
        
        try:
            # Add cache metadata
            index_data["cached_at"] = datetime.now(timezone.utc).isoformat()
            
            # Save index file locally
            with open(self.overall_notes_index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
            
            # Calculate checksum for integrity validation
            checksum = self._calculate_file_checksum(self.overall_notes_index_file)
            
            # Update cache info
            cache_info = self._load_cache_info()
            cache_info['last_sync'] = datetime.now(timezone.utc).isoformat()
            cache_info['total_notes'] = len(index_data.get('notes', []))
            cache_info['cache_size_bytes'] = self._calculate_cache_size()
            cache_info['integrity_check']['checksum'] = checksum
            cache_info['integrity_check']['last_validated'] = datetime.now(timezone.utc).isoformat()
            cache_info['integrity_check']['status'] = 'valid'
            self._save_cache_info(cache_info)
            
            logger.info(f"Cache index updated with {cache_info['total_notes']} notes")
            
        except Exception as e:
            logger.error(f"Failed to update cache index: {e}")
            raise
        finally:
            self._release_lock()
    
    def validate_cache(self) -> bool:
        """
        Validate cache integrity by checking the index file.
        
        Returns:
            bool: True if cache is valid, False otherwise
        """
        if not self._acquire_lock():
            logger.error("Could not acquire lock for cache validation")
            return False
        
        try:
            # Check if index file exists
            if not self.overall_notes_index_file.exists():
                logger.warning("Notes index file does not exist")
                return False
            
            # Load and validate index structure
            try:
                with open(self.overall_notes_index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                
                # Validate required fields
                required_fields = ['version', 'last_updated', 'total_notes', 'notes']
                if not all(field in index_data for field in required_fields):
                    logger.error("Notes index missing required fields")
                    return False
                
                # Validate notes structure
                notes = index_data.get('notes', [])
                for note in notes:
                    required_note_fields = ['id', 'title', 'short_code', 'created_at', 'updated_at']
                    if not all(field in note for field in required_note_fields):
                        logger.error(f"Note missing required fields: {note}")
                        return False
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in notes index file: {e}")
                return False
            
            # Validate checksum if available
            cache_info = self._load_cache_info()
            expected_checksum = cache_info.get('integrity_check', {}).get('checksum')
            
            if expected_checksum:
                actual_checksum = self._calculate_file_checksum(self.overall_notes_index_file)
                if actual_checksum != expected_checksum:
                    logger.error("Notes index checksum mismatch")
                    return False
            
            # Update cache info with validation results
            cache_info['integrity_check'] = {
                "last_validated": datetime.now(timezone.utc).isoformat(),
                "status": "valid",
                "checksum": expected_checksum or self._calculate_file_checksum(self.overall_notes_index_file)
            }
            self._save_cache_info(cache_info)
            
            logger.info("Notes cache validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate notes cache: {e}")
            return False
        finally:
            self._release_lock()
    
    def clear_cache(self) -> None:
        """Clear all cached notes data."""
        if not self._acquire_lock():
            logger.error("Could not acquire lock for cache clearing")
            return
        
        try:
            # Remove index file
            if self.overall_notes_index_file.exists():
                self.overall_notes_index_file.unlink()
            
            # Reset cache info
            cache_info = {
                "version": "1.0",
                "last_sync": None,
                "cache_size_bytes": 0,
                "total_notes": 0,
                "integrity_check": {
                    "last_validated": datetime.now(timezone.utc).isoformat(),
                    "status": "cleared",
                    "checksum": None
                }
            }
            self._save_cache_info(cache_info)
            
            logger.info("Notes cache cleared successfully")
            
        except Exception as e:
            logger.error(f"Failed to clear notes cache: {e}")
            raise
        finally:
            self._release_lock()
    
    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics and status information.
        
        Returns:
            Dict: Cache statistics including size, note count, and status
        """
        try:
            cache_info = self._load_cache_info()
            
            # Update cache size
            cache_info['cache_size_bytes'] = self._calculate_cache_size()
            
            # Get actual note count from index file
            actual_notes_count = 0
            if self.overall_notes_index_file.exists():
                try:
                    with open(self.overall_notes_index_file, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                    actual_notes_count = len(index_data.get('notes', []))
                except Exception:
                    pass
            
            cache_info['actual_notes_count'] = actual_notes_count
            
            # Add cache directory paths for debugging
            cache_info['cache_paths'] = {
                'cache_dir': str(self.cache_dir),
                'overall_notes_index_file': str(self.overall_notes_index_file),
                'cache_info_file': str(self.cache_info_file),
                'cache_lock_file': str(self.cache_lock_file)
            }
            
            # Add cache status summary
            cache_info['cache_status'] = {
                'index_exists': self.overall_notes_index_file.exists(),
                'cache_size_mb': round(cache_info['cache_size_bytes'] / (1024 * 1024), 2),
                'is_valid': cache_info.get('integrity_check', {}).get('status') == 'valid'
            }
            
            # Add cache_size_mb to top level for backward compatibility
            cache_info['cache_size_mb'] = cache_info['cache_status']['cache_size_mb']
            
            return cache_info
            
        except Exception as e:
            logger.error(f"Failed to get notes cache stats: {e}")
            return {
                "version": "1.0",
                "error": str(e),
                "cache_size_bytes": 0,
                "total_notes": 0,
                "actual_notes_count": 0
            }