"""
MetaCacheManager - Manages local metadata caching and synchronization logic.

This module provides caching functionality for cloud session metadata to improve
UI loading performance by avoiding the need to download full session files
just to display basic information.
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


class MetaCacheManager:
    """Manages local metadata caching and synchronization logic."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize MetaCacheManager with cache directory.
        
        Args:
            cache_dir: Optional custom cache directory. If None, uses default ~/.fastshot/
        """
        if cache_dir is None:
            # Use default cache directory in user home
            home_dir = Path.home()
            self.cache_dir = home_dir / ".fastshot"
        else:
            self.cache_dir = Path(cache_dir)
        
        # Create cache directory structure
        self.meta_cache_dir = self.cache_dir / "meta_cache"
        self.meta_indexes_dir = self.meta_cache_dir / "meta_indexes"
        self.sessions_cache_dir = self.cache_dir / "sessions"
        
        # Ensure sessions cache directory is the same as CloudSyncManager's local_sessions_dir
        # This creates a unified caching system
        self.sessions_cache_dir = Path.home() / "fastshot_sessions"
        
        # Cache files
        self.overall_meta_file = self.meta_cache_dir / "overall_meta.json"
        self.cache_info_file = self.meta_cache_dir / "cache_info.json"
        self.cache_lock_file = self.cache_dir / "cache_lock"
        
        # Ensure directories exist
        self._create_cache_directories()
        
        # Initialize cache info if it doesn't exist
        self._initialize_cache_info()
    
    def _create_cache_directories(self):
        """Create cache directory structure if it doesn't exist."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.meta_cache_dir.mkdir(parents=True, exist_ok=True)
            self.meta_indexes_dir.mkdir(parents=True, exist_ok=True)
            self.sessions_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Cache directories created at {self.cache_dir}")
        except Exception as e:
            logger.error(f"Failed to create cache directories: {e}")
            raise
    
    def _initialize_cache_info(self):
        """Initialize cache info file with default values if it doesn't exist."""
        if not self.cache_info_file.exists():
            cache_info = {
                "version": "1.0",
                "last_sync": None,
                "cache_size_bytes": 0,
                "total_meta_files": 0,
                "integrity_check": {
                    "last_validated": None,
                    "status": "unknown",
                    "corrupted_files": []
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
                # Windows file locking
                msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            
            # Write process info to lock file
            self._lock_fd.write(f"pid:{os.getpid()}\ntime:{datetime.now().isoformat()}\n")
            self._lock_fd.flush()
            
            logger.debug("Cache lock acquired")
            return True
        except (IOError, OSError) as e:
            logger.warning(f"Failed to acquire cache lock: {e}")
            if hasattr(self, '_lock_fd') and self._lock_fd:
                self._lock_fd.close()
            return False
    
    def _release_lock(self):
        """Release file lock."""
        try:
            if hasattr(self, '_lock_fd') and self._lock_fd:
                if HAS_FCNTL:
                    # Unix/Linux file unlocking
                    fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                else:
                    # Windows file unlocking - unlock before closing
                    try:
                        msvcrt.locking(self._lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass  # File might already be unlocked
                
                self._lock_fd.close()
                self._lock_fd = None
                logger.debug("Cache lock released")
        except Exception as e:
            logger.warning(f"Error releasing cache lock: {e}")
            # Ensure file handle is closed even if unlocking fails
            if hasattr(self, '_lock_fd') and self._lock_fd:
                try:
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
            logger.error(f"Failed to load cache info: {e}")
        
        # Return default cache info if loading fails
        return {
            "version": "1.0",
            "last_sync": None,
            "cache_size_bytes": 0,
            "total_meta_files": 0,
            "integrity_check": {
                "last_validated": None,
                "status": "unknown",
                "corrupted_files": []
            }
        }
    
    def _save_cache_info(self, cache_info: Dict[str, Any]):
        """Save cache info to file."""
        try:
            with open(self.cache_info_file, 'w', encoding='utf-8') as f:
                json.dump(cache_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache info: {e}")
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
            # Calculate metadata cache size
            for root, dirs, files in os.walk(self.meta_cache_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.exists():
                        total_size += file_path.stat().st_size
            
            # Calculate session files cache size
            if self.sessions_cache_dir.exists():
                for session_file in self.sessions_cache_dir.glob("*.fastshot"):
                    if session_file.exists():
                        total_size += session_file.stat().st_size
                        
        except Exception as e:
            logger.error(f"Failed to calculate cache size: {e}")
        return total_size
    
    def get_cached_metadata(self) -> List[Dict]:
        """
        Get cached session metadata from local cache.
        
        Returns:
            List[Dict]: List of cached session metadata dictionaries
        """
        if not self._acquire_lock():
            logger.warning("Could not acquire lock for reading cached metadata")
            return []
        
        try:
            cached_metadata = []
            
            # Load overall metadata file if it exists
            if self.overall_meta_file.exists():
                try:
                    with open(self.overall_meta_file, 'r', encoding='utf-8') as f:
                        overall_meta = json.load(f)
                    
                    # Load individual metadata files for each session
                    for session_info in overall_meta.get('sessions', []):
                        filename = session_info.get('filename', '')
                        if filename:
                            meta_data = self.load_meta_index(filename)
                            if meta_data:
                                cached_metadata.append(meta_data)
                
                except Exception as e:
                    logger.error(f"Failed to load overall metadata: {e}")
            
            logger.info(f"Loaded {len(cached_metadata)} cached metadata entries")
            return cached_metadata
            
        finally:
            self._release_lock()
    
    def update_cache_from_cloud(self, overall_meta: Dict) -> None:
        """
        Update local cache based on cloud overall metadata file.
        
        Args:
            overall_meta: Overall metadata dictionary from cloud
        """
        if not self._acquire_lock():
            logger.error("Could not acquire lock for cache update")
            return
        
        try:
            # Save overall metadata file locally
            with open(self.overall_meta_file, 'w', encoding='utf-8') as f:
                json.dump(overall_meta, f, indent=2, ensure_ascii=False)
            
            # Update cache info
            cache_info = self._load_cache_info()
            cache_info['last_sync'] = datetime.now(timezone.utc).isoformat()
            cache_info['total_meta_files'] = len(overall_meta.get('sessions', []))
            cache_info['cache_size_bytes'] = self._calculate_cache_size()
            self._save_cache_info(cache_info)
            
            logger.info(f"Cache updated with {cache_info['total_meta_files']} sessions")
            
        except Exception as e:
            logger.error(f"Failed to update cache from cloud: {e}")
            raise
        finally:
            self._release_lock()
    
    def save_meta_index(self, filename: str, metadata: Dict) -> None:
        """
        Save metadata index file for a specific session.
        
        Args:
            filename: Session filename (e.g., "20250621114615_tt1.fastshot")
            metadata: Metadata dictionary to save
        """
        if not self._acquire_lock():
            logger.error("Could not acquire lock for saving meta index")
            return
        
        try:
            # Create meta index filename
            base_name = filename.replace('.fastshot', '')
            meta_filename = f"{base_name}.meta.json"
            meta_file_path = self.meta_indexes_dir / meta_filename
            
            # Prepare meta index data
            meta_index_data = {
                "version": "1.0",
                "filename": filename,
                "metadata": metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            # Save meta index file
            with open(meta_file_path, 'w', encoding='utf-8') as f:
                json.dump(meta_index_data, f, indent=2, ensure_ascii=False)
            
            # Calculate and add checksum
            checksum = self._calculate_file_checksum(meta_file_path)
            meta_index_data['checksum'] = checksum
            
            # Re-save with checksum
            with open(meta_file_path, 'w', encoding='utf-8') as f:
                json.dump(meta_index_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved meta index for {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save meta index for {filename}: {e}")
            raise
        finally:
            self._release_lock()
    
    def load_meta_index(self, filename: str) -> Optional[Dict]:
        """
        Load metadata index file for a specific session.
        
        Args:
            filename: Session filename (e.g., "20250621114615_tt1.fastshot")
            
        Returns:
            Optional[Dict]: Metadata dictionary if found, None otherwise
        """
        try:
            # Create meta index filename
            base_name = filename.replace('.fastshot', '')
            meta_filename = f"{base_name}.meta.json"
            meta_file_path = self.meta_indexes_dir / meta_filename
            
            if not meta_file_path.exists():
                return None
            
            # Load meta index file
            with open(meta_file_path, 'r', encoding='utf-8') as f:
                meta_index_data = json.load(f)
            
            # Validate checksum if present
            if 'checksum' in meta_index_data:
                expected_checksum = meta_index_data['checksum']
                # Temporarily remove checksum for validation
                temp_data = meta_index_data.copy()
                del temp_data['checksum']
                
                # Save temp file and calculate checksum
                temp_file = meta_file_path.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(temp_data, f, indent=2, ensure_ascii=False)
                
                actual_checksum = self._calculate_file_checksum(temp_file)
                temp_file.unlink()  # Clean up temp file
                
                if actual_checksum != expected_checksum:
                    logger.warning(f"Checksum mismatch for {filename} meta index")
                    return None
            
            return meta_index_data
            
        except Exception as e:
            logger.error(f"Failed to load meta index for {filename}: {e}")
            return None
    
    def validate_cache_integrity(self) -> bool:
        """
        Validate cache integrity by checking all metadata files.
        
        Returns:
            bool: True if cache is valid, False otherwise
        """
        if not self._acquire_lock():
            logger.error("Could not acquire lock for cache validation")
            return False
        
        try:
            corrupted_files = []
            total_files = 0
            
            # Check all meta index files
            if self.meta_indexes_dir.exists():
                for meta_file in self.meta_indexes_dir.glob("*.meta.json"):
                    total_files += 1
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta_data = json.load(f)
                        
                        # Validate required fields
                        required_fields = ['version', 'filename', 'metadata', 'created_at']
                        if not all(field in meta_data for field in required_fields):
                            corrupted_files.append(str(meta_file.name))
                            continue
                        
                        # Validate checksum if present
                        if 'checksum' in meta_data:
                            expected_checksum = meta_data['checksum']
                            temp_data = meta_data.copy()
                            del temp_data['checksum']
                            
                            temp_file = meta_file.with_suffix('.tmp')
                            with open(temp_file, 'w', encoding='utf-8') as f:
                                json.dump(temp_data, f, indent=2, ensure_ascii=False)
                            
                            actual_checksum = self._calculate_file_checksum(temp_file)
                            temp_file.unlink()
                            
                            if actual_checksum != expected_checksum:
                                corrupted_files.append(str(meta_file.name))
                    
                    except Exception as e:
                        logger.error(f"Error validating {meta_file}: {e}")
                        corrupted_files.append(str(meta_file.name))
            
            # Update cache info with validation results
            cache_info = self._load_cache_info()
            cache_info['integrity_check'] = {
                "last_validated": datetime.now(timezone.utc).isoformat(),
                "status": "valid" if not corrupted_files else "corrupted",
                "corrupted_files": corrupted_files
            }
            self._save_cache_info(cache_info)
            
            is_valid = len(corrupted_files) == 0
            logger.info(f"Cache validation complete: {total_files} files checked, "
                       f"{len(corrupted_files)} corrupted, valid: {is_valid}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to validate cache integrity: {e}")
            return False
        finally:
            self._release_lock()
    
    def clear_cache(self) -> None:
        """Clear all cached metadata files."""
        if not self._acquire_lock():
            logger.error("Could not acquire lock for cache clearing")
            return
        
        try:
            # Remove all meta index files
            if self.meta_indexes_dir.exists():
                for meta_file in self.meta_indexes_dir.glob("*.meta.json"):
                    meta_file.unlink()
            
            # Remove overall meta file
            if self.overall_meta_file.exists():
                self.overall_meta_file.unlink()
            
            # Reset cache info
            cache_info = {
                "version": "1.0",
                "last_sync": None,
                "cache_size_bytes": 0,
                "total_meta_files": 0,
                "integrity_check": {
                    "last_validated": datetime.now(timezone.utc).isoformat(),
                    "status": "cleared",
                    "corrupted_files": []
                }
            }
            self._save_cache_info(cache_info)
            
            logger.info("Cache cleared successfully")
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise
        finally:
            self._release_lock()
    
    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics and status information.
        
        Returns:
            Dict: Cache statistics including size, file count, and status
        """
        try:
            cache_info = self._load_cache_info()
            
            # Update cache size
            cache_info['cache_size_bytes'] = self._calculate_cache_size()
            
            # Count actual meta files
            actual_meta_files = 0
            if self.meta_indexes_dir.exists():
                actual_meta_files = len(list(self.meta_indexes_dir.glob("*.meta.json")))
            
            cache_info['actual_meta_files'] = actual_meta_files
            
            # Add cache directory paths for debugging
            cache_info['cache_paths'] = {
                'cache_dir': str(self.cache_dir),
                'meta_cache_dir': str(self.meta_cache_dir),
                'meta_indexes_dir': str(self.meta_indexes_dir),
                'overall_meta_file': str(self.overall_meta_file),
                'cache_info_file': str(self.cache_info_file)
            }
            
            return cache_info
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "version": "1.0",
                "error": str(e),
                "cache_size_bytes": 0,
                "total_meta_files": 0,
                "actual_meta_files": 0
            }
    
    def smart_sync_with_cloud(self, overall_meta: Dict, cloud_sync_manager, 
                             orphan_callback=None, progress_callback=None) -> Dict:
        """
        Smart cache synchronization using filename-based comparison.
        
        Args:
            overall_meta: Overall metadata dictionary from cloud
            cloud_sync_manager: CloudSyncManager instance for downloading missing files
            orphan_callback: Callback function for handling orphaned local cache entries
            progress_callback: Callback function for progress updates
            
        Returns:
            Dict: Synchronization results with statistics
        """
        if not self._acquire_lock():
            logger.error("Could not acquire lock for smart cache sync")
            return {"success": False, "error": "Could not acquire cache lock"}
        
        try:
            if progress_callback:
                progress_callback(0, "Starting smart cache synchronization...")
            
            # Get cloud session filenames from overall metadata
            cloud_filenames = set()
            cloud_sessions = overall_meta.get('sessions', [])
            for session in cloud_sessions:
                filename = session.get('filename', '')
                if filename:
                    cloud_filenames.add(filename)
            
            # Get local cache filenames
            local_filenames = set()
            if self.meta_indexes_dir.exists():
                for meta_file in self.meta_indexes_dir.glob("*.meta.json"):
                    # Extract original filename from meta filename
                    base_name = meta_file.stem.replace('.meta', '')
                    original_filename = f"{base_name}.fastshot"
                    local_filenames.add(original_filename)
            
            if progress_callback:
                progress_callback(10, f"Found {len(cloud_filenames)} cloud sessions, {len(local_filenames)} cached sessions")
            
            # Find missing sessions (in cloud but not in cache)
            missing_sessions = cloud_filenames - local_filenames
            
            # Find orphaned sessions (in cache but not in cloud)
            orphaned_sessions = local_filenames - cloud_filenames
            
            logger.info(f"Smart sync analysis: {len(missing_sessions)} missing, {len(orphaned_sessions)} orphaned")
            
            sync_results = {
                "success": True,
                "cloud_sessions": len(cloud_filenames),
                "cached_sessions": len(local_filenames),
                "missing_sessions": len(missing_sessions),
                "orphaned_sessions": len(orphaned_sessions),
                "downloaded": [],
                "deleted": [],
                "errors": []
            }
            
            # Download missing lightweight index files
            if missing_sessions:
                if progress_callback:
                    progress_callback(20, f"Downloading {len(missing_sessions)} missing metadata files...")
                
                downloaded_count = 0
                for i, filename in enumerate(missing_sessions):
                    try:
                        # Update progress
                        progress = 20 + (i / len(missing_sessions)) * 50
                        if progress_callback:
                            progress_callback(progress, f"Downloading metadata for {filename}...")
                        
                        # Load metadata index from cloud
                        meta_index = cloud_sync_manager.load_meta_index_from_cloud(filename)
                        if meta_index:
                            # Save to local cache
                            metadata = meta_index.get('metadata', {})
                            self.save_meta_index(filename, metadata)
                            sync_results["downloaded"].append(filename)
                            downloaded_count += 1
                            logger.info(f"Downloaded metadata for {filename}")
                        else:
                            # Create basic metadata from overall meta info
                            session_info = next((s for s in cloud_sessions if s.get('filename') == filename), {})
                            basic_metadata = {
                                'name': '',
                                'desc': 'Metadata not available',
                                'tags': [],
                                'color': '',
                                'class': '',
                                'image_count': 0,
                                'file_size': session_info.get('file_size', 0),
                                'created_at': session_info.get('created_at', datetime.now(timezone.utc).isoformat()),
                                'thumbnail_collage': None
                            }
                            self.save_meta_index(filename, basic_metadata)
                            sync_results["downloaded"].append(filename)
                            downloaded_count += 1
                            logger.info(f"Created basic metadata for {filename}")
                    
                    except Exception as e:
                        error_msg = f"Failed to download metadata for {filename}: {e}"
                        logger.error(error_msg)
                        sync_results["errors"].append(error_msg)
                
                logger.info(f"Downloaded metadata for {downloaded_count}/{len(missing_sessions)} missing sessions")
            
            # Handle orphaned local cache entries
            if orphaned_sessions:
                if progress_callback:
                    progress_callback(70, f"Processing {len(orphaned_sessions)} orphaned cache entries...")
                
                deleted_count = 0
                for i, filename in enumerate(orphaned_sessions):
                    try:
                        # Update progress
                        progress = 70 + (i / len(orphaned_sessions)) * 20
                        if progress_callback:
                            progress_callback(progress, f"Processing orphaned entry: {filename}...")
                        
                        # Ask user what to do with orphaned entry
                        should_delete = True  # Default action
                        if orphan_callback:
                            try:
                                should_delete = orphan_callback(filename)
                            except Exception as e:
                                logger.error(f"Error in orphan callback for {filename}: {e}")
                        
                        if should_delete:
                            # Delete orphaned cache entry
                            base_name = filename.replace('.fastshot', '')
                            meta_filename = f"{base_name}.meta.json"
                            meta_file_path = self.meta_indexes_dir / meta_filename
                            
                            if meta_file_path.exists():
                                meta_file_path.unlink()
                                sync_results["deleted"].append(filename)
                                deleted_count += 1
                                logger.info(f"Deleted orphaned cache entry for {filename}")
                    
                    except Exception as e:
                        error_msg = f"Failed to process orphaned entry {filename}: {e}"
                        logger.error(error_msg)
                        sync_results["errors"].append(error_msg)
                
                logger.info(f"Processed {deleted_count}/{len(orphaned_sessions)} orphaned cache entries")
            
            # Update overall metadata file locally
            if progress_callback:
                progress_callback(90, "Updating local cache metadata...")
            
            self.update_cache_from_cloud(overall_meta)
            
            # Validate cache integrity
            if progress_callback:
                progress_callback(95, "Validating cache integrity...")
            
            cache_valid = self.validate_cache_integrity()
            sync_results["cache_valid"] = cache_valid
            
            if progress_callback:
                progress_callback(100, "Smart cache synchronization completed")
            
            logger.info(f"Smart cache sync completed: {sync_results}")
            return sync_results
            
        except Exception as e:
            error_msg = f"Failed to perform smart cache sync: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        finally:
            self._release_lock()
    
    def cleanup_cache_with_validation(self, progress_callback=None) -> Dict:
        """
        Perform cache cleanup and validation with detailed feedback.
        
        Args:
            progress_callback: Callback function for progress updates
            
        Returns:
            Dict: Cleanup results with statistics
        """
        if not self._acquire_lock():
            return {"success": False, "error": "Could not acquire cache lock"}
        
        try:
            if progress_callback:
                progress_callback(0, "Starting cache cleanup and validation...")
            
            cleanup_results = {
                "success": True,
                "files_validated": 0,
                "files_repaired": 0,
                "files_deleted": 0,
                "cache_size_before": 0,
                "cache_size_after": 0,
                "errors": []
            }
            
            # Get initial cache size
            cleanup_results["cache_size_before"] = self._calculate_cache_size()
            
            if progress_callback:
                progress_callback(10, "Validating cache integrity...")
            
            # Validate cache integrity first
            corrupted_files = []
            total_files = 0
            
            if self.meta_indexes_dir.exists():
                meta_files = list(self.meta_indexes_dir.glob("*.meta.json"))
                total_files = len(meta_files)
                
                for i, meta_file in enumerate(meta_files):
                    try:
                        progress = 10 + (i / total_files) * 40
                        if progress_callback:
                            progress_callback(progress, f"Validating {meta_file.name}...")
                        
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            meta_data = json.load(f)
                        
                        # Validate required fields
                        required_fields = ['version', 'filename', 'metadata', 'created_at']
                        if not all(field in meta_data for field in required_fields):
                            corrupted_files.append(meta_file)
                            continue
                        
                        # Validate checksum if present
                        if 'checksum' in meta_data:
                            expected_checksum = meta_data['checksum']
                            temp_data = meta_data.copy()
                            del temp_data['checksum']
                            
                            temp_file = meta_file.with_suffix('.tmp')
                            with open(temp_file, 'w', encoding='utf-8') as f:
                                json.dump(temp_data, f, indent=2, ensure_ascii=False)
                            
                            actual_checksum = self._calculate_file_checksum(temp_file)
                            temp_file.unlink()
                            
                            if actual_checksum != expected_checksum:
                                corrupted_files.append(meta_file)
                        
                        cleanup_results["files_validated"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error validating {meta_file}: {e}")
                        corrupted_files.append(meta_file)
                        cleanup_results["errors"].append(f"Validation error for {meta_file.name}: {e}")
            
            if progress_callback:
                progress_callback(50, f"Found {len(corrupted_files)} corrupted files...")
            
            # Handle corrupted files
            for i, corrupt_file in enumerate(corrupted_files):
                try:
                    progress = 50 + (i / len(corrupted_files)) * 30 if corrupted_files else 50
                    if progress_callback:
                        progress_callback(progress, f"Removing corrupted file {corrupt_file.name}...")
                    
                    corrupt_file.unlink()
                    cleanup_results["files_deleted"] += 1
                    logger.info(f"Deleted corrupted cache file: {corrupt_file}")
                    
                except Exception as e:
                    logger.error(f"Error deleting corrupted file {corrupt_file}: {e}")
                    cleanup_results["errors"].append(f"Could not delete {corrupt_file.name}: {e}")
            
            if progress_callback:
                progress_callback(80, "Cleaning up orphaned files...")
            
            # Clean up any orphaned temporary files
            if self.meta_cache_dir.exists():
                for temp_file in self.meta_cache_dir.rglob("*.tmp"):
                    try:
                        temp_file.unlink()
                        logger.info(f"Cleaned up temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Could not clean up temporary file {temp_file}: {e}")
            
            if progress_callback:
                progress_callback(90, "Updating cache info...")
            
            # Update cache info
            cache_info = self._load_cache_info()
            cache_info['integrity_check'] = {
                "last_validated": datetime.now(timezone.utc).isoformat(),
                "status": "cleaned" if corrupted_files else "valid",
                "corrupted_files": []
            }
            cache_info['cache_size_bytes'] = self._calculate_cache_size()
            cache_info['total_meta_files'] = cleanup_results["files_validated"]
            self._save_cache_info(cache_info)
            
            cleanup_results["cache_size_after"] = cache_info['cache_size_bytes']
            
            if progress_callback:
                progress_callback(100, "Cache cleanup completed")
            
            logger.info(f"Cache cleanup completed: {cleanup_results}")
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self._release_lock()
    
    def recover_from_corruption(self, cloud_sync_manager=None, progress_callback=None) -> Dict:
        """
        Recover cache from corruption by rebuilding from cloud or clearing.
        
        Args:
            cloud_sync_manager: CloudSyncManager instance for rebuilding from cloud
            progress_callback: Callback function for progress updates
            
        Returns:
            Dict: Recovery results
        """
        if not self._acquire_lock():
            return {"success": False, "error": "Could not acquire cache lock"}
        
        try:
            if progress_callback:
                progress_callback(0, "Starting cache recovery...")
            
            recovery_results = {
                "success": True,
                "recovery_method": "unknown",
                "sessions_recovered": 0,
                "errors": []
            }
            
            # Try to recover from cloud if available
            if cloud_sync_manager and cloud_sync_manager.cloud_sync_enabled:
                if progress_callback:
                    progress_callback(10, "Attempting recovery from cloud...")
                
                try:
                    # Clear corrupted cache
                    self.clear_cache()
                    
                    # Load overall metadata from cloud
                    overall_meta = cloud_sync_manager.load_overall_meta_file()
                    if overall_meta:
                        # Rebuild cache from cloud metadata
                        cloud_sessions = overall_meta.get('sessions', [])
                        
                        for i, session_info in enumerate(cloud_sessions):
                            try:
                                progress = 10 + (i / len(cloud_sessions)) * 80
                                filename = session_info.get('filename', '')
                                if progress_callback:
                                    progress_callback(progress, f"Recovering {filename}...")
                                
                                # Try to load metadata index from cloud
                                meta_index = cloud_sync_manager.load_meta_index_from_cloud(filename)
                                if meta_index:
                                    metadata = meta_index.get('metadata', {})
                                    self.save_meta_index(filename, metadata)
                                    recovery_results["sessions_recovered"] += 1
                                else:
                                    # Create basic metadata from session info
                                    basic_metadata = {
                                        'name': '',
                                        'desc': 'Recovered session',
                                        'tags': [],
                                        'color': '',
                                        'class': '',
                                        'image_count': 0,
                                        'file_size': session_info.get('file_size', 0),
                                        'created_at': session_info.get('created_at', datetime.now(timezone.utc).isoformat()),
                                        'thumbnail_collage': None
                                    }
                                    self.save_meta_index(filename, basic_metadata)
                                    recovery_results["sessions_recovered"] += 1
                                
                            except Exception as e:
                                logger.error(f"Error recovering session {filename}: {e}")
                                recovery_results["errors"].append(f"Recovery error for {filename}: {e}")
                        
                        # Update overall metadata cache
                        self.update_cache_from_cloud(overall_meta)
                        recovery_results["recovery_method"] = "cloud_rebuild"
                        
                        if progress_callback:
                            progress_callback(90, "Cloud recovery completed")
                    
                    else:
                        raise Exception("Could not load overall metadata from cloud")
                
                except Exception as e:
                    logger.error(f"Cloud recovery failed: {e}")
                    recovery_results["errors"].append(f"Cloud recovery failed: {e}")
                    # Fall back to cache clearing
                    recovery_results["recovery_method"] = "cache_clear_fallback"
                    self.clear_cache()
            
            else:
                # No cloud sync available, just clear cache
                if progress_callback:
                    progress_callback(50, "Clearing corrupted cache...")
                
                self.clear_cache()
                recovery_results["recovery_method"] = "cache_clear"
            
            if progress_callback:
                progress_callback(100, "Cache recovery completed")
            
            logger.info(f"Cache recovery completed: {recovery_results}")
            return recovery_results
            
        except Exception as e:
            logger.error(f"Error during cache recovery: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self._release_lock()
            logger.error("Could not acquire lock for cache cleanup")
            return {"success": False, "error": "Could not acquire cache lock"}
        
        try:
            if progress_callback:
                progress_callback(0, "Starting cache cleanup and validation...")
            
            cleanup_results = {
                "success": True,
                "total_files_checked": 0,
                "corrupted_files_found": 0,
                "corrupted_files_removed": 0,
                "orphaned_files_found": 0,
                "orphaned_files_removed": 0,
                "cache_size_before": 0,
                "cache_size_after": 0,
                "errors": []
            }
            
            # Get initial cache size
            cleanup_results["cache_size_before"] = self._calculate_cache_size()
            
            if progress_callback:
                progress_callback(10, "Scanning cache files...")
            
            # Get all meta index files
            meta_files = []
            if self.meta_indexes_dir.exists():
                meta_files = list(self.meta_indexes_dir.glob("*.meta.json"))
            
            cleanup_results["total_files_checked"] = len(meta_files)
            
            if progress_callback:
                progress_callback(20, f"Found {len(meta_files)} cache files to validate...")
            
            # Validate each meta file
            corrupted_files = []
            for i, meta_file in enumerate(meta_files):
                try:
                    # Update progress
                    progress = 20 + (i / len(meta_files)) * 50
                    if progress_callback:
                        progress_callback(progress, f"Validating {meta_file.name}...")
                    
                    # Load and validate meta file
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta_data = json.load(f)
                    
                    # Check required fields
                    required_fields = ['version', 'filename', 'metadata', 'created_at']
                    if not all(field in meta_data for field in required_fields):
                        corrupted_files.append(meta_file)
                        continue
                    
                    # Validate checksum if present
                    if 'checksum' in meta_data:
                        expected_checksum = meta_data['checksum']
                        temp_data = meta_data.copy()
                        del temp_data['checksum']
                        
                        temp_file = meta_file.with_suffix('.tmp')
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(temp_data, f, indent=2, ensure_ascii=False)
                        
                        actual_checksum = self._calculate_file_checksum(temp_file)
                        temp_file.unlink()
                        
                        if actual_checksum != expected_checksum:
                            corrupted_files.append(meta_file)
                
                except Exception as e:
                    logger.error(f"Error validating {meta_file}: {e}")
                    corrupted_files.append(meta_file)
                    cleanup_results["errors"].append(f"Validation error for {meta_file.name}: {e}")
            
            cleanup_results["corrupted_files_found"] = len(corrupted_files)
            
            # Remove corrupted files
            if corrupted_files:
                if progress_callback:
                    progress_callback(70, f"Removing {len(corrupted_files)} corrupted files...")
                
                removed_count = 0
                for corrupted_file in corrupted_files:
                    try:
                        corrupted_file.unlink()
                        removed_count += 1
                        logger.info(f"Removed corrupted cache file: {corrupted_file.name}")
                    except Exception as e:
                        error_msg = f"Failed to remove corrupted file {corrupted_file.name}: {e}"
                        logger.error(error_msg)
                        cleanup_results["errors"].append(error_msg)
                
                cleanup_results["corrupted_files_removed"] = removed_count
            
            # Check for orphaned files (files without corresponding overall metadata entry)
            if progress_callback:
                progress_callback(80, "Checking for orphaned cache files...")
            
            # Load overall metadata to check for orphans
            orphaned_files = []
            if self.overall_meta_file.exists():
                try:
                    with open(self.overall_meta_file, 'r', encoding='utf-8') as f:
                        overall_meta = json.load(f)
                    
                    # Get valid filenames from overall metadata
                    valid_filenames = set()
                    for session in overall_meta.get('sessions', []):
                        filename = session.get('filename', '')
                        if filename:
                            valid_filenames.add(filename)
                    
                    # Check each remaining meta file
                    remaining_meta_files = [f for f in meta_files if f not in corrupted_files]
                    for meta_file in remaining_meta_files:
                        try:
                            with open(meta_file, 'r', encoding='utf-8') as f:
                                meta_data = json.load(f)
                            
                            filename = meta_data.get('filename', '')
                            if filename and filename not in valid_filenames:
                                orphaned_files.append(meta_file)
                        
                        except Exception as e:
                            logger.error(f"Error checking orphan status for {meta_file}: {e}")
                
                except Exception as e:
                    logger.error(f"Error loading overall metadata for orphan check: {e}")
                    cleanup_results["errors"].append(f"Could not check for orphaned files: {e}")
            
            cleanup_results["orphaned_files_found"] = len(orphaned_files)
            
            # Remove orphaned files (optional - could ask user)
            if orphaned_files:
                if progress_callback:
                    progress_callback(90, f"Removing {len(orphaned_files)} orphaned files...")
                
                removed_count = 0
                for orphaned_file in orphaned_files:
                    try:
                        orphaned_file.unlink()
                        removed_count += 1
                        logger.info(f"Removed orphaned cache file: {orphaned_file.name}")
                    except Exception as e:
                        error_msg = f"Failed to remove orphaned file {orphaned_file.name}: {e}"
                        logger.error(error_msg)
                        cleanup_results["errors"].append(error_msg)
                
                cleanup_results["orphaned_files_removed"] = removed_count
            
            # Update cache info with cleanup results
            if progress_callback:
                progress_callback(95, "Updating cache information...")
            
            cache_info = self._load_cache_info()
            cache_info['integrity_check'] = {
                "last_validated": datetime.now(timezone.utc).isoformat(),
                "status": "cleaned" if (corrupted_files or orphaned_files) else "valid",
                "corrupted_files": [],
                "last_cleanup": datetime.now(timezone.utc).isoformat(),
                "cleanup_results": cleanup_results
            }
            cache_info['cache_size_bytes'] = self._calculate_cache_size()
            cache_info['total_meta_files'] = len(list(self.meta_indexes_dir.glob("*.meta.json"))) if self.meta_indexes_dir.exists() else 0
            self._save_cache_info(cache_info)
            
            cleanup_results["cache_size_after"] = cache_info['cache_size_bytes']
            
            if progress_callback:
                progress_callback(100, "Cache cleanup and validation completed")
            
            logger.info(f"Cache cleanup completed: {cleanup_results}")
            return cleanup_results
            
        except Exception as e:
            error_msg = f"Failed to perform cache cleanup: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        finally:
            self._release_lock()
    
    def get_local_cache_filenames(self) -> set:
        """
        Get set of filenames that exist in local cache.
        
        Returns:
            set: Set of session filenames that have cached metadata
        """
        local_filenames = set()
        try:
            if self.meta_indexes_dir.exists():
                for meta_file in self.meta_indexes_dir.glob("*.meta.json"):
                    # Extract original filename from meta filename
                    base_name = meta_file.stem.replace('.meta', '')
                    original_filename = f"{base_name}.fastshot"
                    local_filenames.add(original_filename)
        except Exception as e:
            logger.error(f"Error getting local cache filenames: {e}")
        
        return local_filenames   
 
    def get_cached_session_files(self) -> List[str]:
        """
        Get list of cached session files.
        
        Returns:
            List[str]: List of cached session filenames
        """
        try:
            cached_files = []
            if self.sessions_cache_dir.exists():
                for session_file in self.sessions_cache_dir.glob("*.fastshot"):
                    cached_files.append(session_file.name)
            return cached_files
        except Exception as e:
            logger.error(f"Failed to get cached session files: {e}")
            return []
    
    def is_session_cached(self, filename: str) -> bool:
        """
        Check if a session file is cached locally.
        
        Args:
            filename: Session filename to check
            
        Returns:
            bool: True if session is cached, False otherwise
        """
        try:
            session_path = self.sessions_cache_dir / filename
            return session_path.exists()
        except Exception as e:
            logger.error(f"Failed to check if session is cached: {e}")
            return False
    
    def get_session_cache_info(self, filename: str) -> Optional[Dict]:
        """
        Get cache information for a specific session file.
        
        Args:
            filename: Session filename
            
        Returns:
            Optional[Dict]: Cache info including size, modification time, etc.
        """
        try:
            session_path = self.sessions_cache_dir / filename
            if not session_path.exists():
                return None
            
            stat = session_path.stat()
            return {
                'filename': filename,
                'size': stat.st_size,
                'cached_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'path': str(session_path)
            }
        except Exception as e:
            logger.error(f"Failed to get session cache info for {filename}: {e}")
            return None
    
    def clear_session_cache(self, filename: Optional[str] = None) -> bool:
        """
        Clear session file cache.
        
        Args:
            filename: Optional specific filename to clear. If None, clears all session cache.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if filename:
                # Clear specific session file
                session_path = self.sessions_cache_dir / filename
                if session_path.exists():
                    session_path.unlink()
                    logger.info(f"Cleared cached session: {filename}")
                    return True
                else:
                    logger.warning(f"Session not found in cache: {filename}")
                    return False
            else:
                # Clear all session cache files
                if self.sessions_cache_dir.exists():
                    cleared_count = 0
                    for session_file in self.sessions_cache_dir.glob("*.fastshot"):
                        try:
                            session_file.unlink()
                            cleared_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete cached session {session_file.name}: {e}")
                    
                    logger.info(f"Cleared {cleared_count} cached session files")
                    return True
                
            return True
        except Exception as e:
            logger.error(f"Failed to clear session cache: {e}")
            return False
    
    def get_cache_statistics(self) -> Dict:
        """
        Get comprehensive cache statistics including both metadata and session files.
        
        Returns:
            Dict: Detailed cache statistics
        """
        try:
            # Get basic cache stats
            cache_stats = self.get_cache_stats()
            
            # Add session file statistics
            cached_sessions = self.get_cached_session_files()
            session_cache_size = 0
            
            for filename in cached_sessions:
                session_info = self.get_session_cache_info(filename)
                if session_info:
                    session_cache_size += session_info['size']
            
            cache_stats.update({
                'cached_session_files': len(cached_sessions),
                'session_cache_size_bytes': session_cache_size,
                'session_cache_size_mb': session_cache_size / (1024 * 1024),
                'total_cache_size_mb': cache_stats.get('cache_size_bytes', 0) / (1024 * 1024),
                'cached_sessions': cached_sessions
            })
            
            return cache_stats
            
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return {'error': str(e)}
    
    def optimize_session_cache(self, max_size_mb: int = 500, max_age_days: int = 30) -> Dict:
        """
        Optimize session cache by removing old or large files.
        
        Args:
            max_size_mb: Maximum cache size in MB
            max_age_days: Maximum age of cached files in days
            
        Returns:
            Dict: Optimization results
        """
        try:
            if not self.sessions_cache_dir.exists():
                return {"success": True, "message": "No session cache to optimize"}
            
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 3600
            max_size_bytes = max_size_mb * 1024 * 1024
            
            # Get all session files with their info
            session_files = []
            total_size = 0
            
            for session_file in self.sessions_cache_dir.glob("*.fastshot"):
                try:
                    stat = session_file.stat()
                    age_seconds = current_time - stat.st_mtime
                    
                    session_files.append({
                        'path': session_file,
                        'name': session_file.name,
                        'size': stat.st_size,
                        'age_seconds': age_seconds,
                        'last_modified': stat.st_mtime
                    })
                    total_size += stat.st_size
                    
                except Exception as e:
                    logger.error(f"Error getting info for {session_file}: {e}")
            
            # Sort by last modified time (oldest first)
            session_files.sort(key=lambda x: x['last_modified'])
            
            deleted_files = []
            deleted_size = 0
            
            # Remove files that are too old
            for file_info in session_files[:]:
                if file_info['age_seconds'] > max_age_seconds:
                    try:
                        file_info['path'].unlink()
                        deleted_files.append(file_info['name'])
                        deleted_size += file_info['size']
                        total_size -= file_info['size']
                        session_files.remove(file_info)
                        logger.info(f"Deleted old cached session: {file_info['name']}")
                    except Exception as e:
                        logger.error(f"Failed to delete old session {file_info['name']}: {e}")
            
            # Remove oldest files if cache is still too large
            while total_size > max_size_bytes and session_files:
                oldest_file = session_files.pop(0)
                try:
                    oldest_file['path'].unlink()
                    deleted_files.append(oldest_file['name'])
                    deleted_size += oldest_file['size']
                    total_size -= oldest_file['size']
                    logger.info(f"Deleted large cached session: {oldest_file['name']}")
                except Exception as e:
                    logger.error(f"Failed to delete large session {oldest_file['name']}: {e}")
            
            return {
                "success": True,
                "deleted_files": len(deleted_files),
                "deleted_size_mb": deleted_size / (1024 * 1024),
                "remaining_files": len(session_files),
                "remaining_size_mb": total_size / (1024 * 1024),
                "deleted_filenames": deleted_files
            }
            
        except Exception as e:
            logger.error(f"Failed to optimize session cache: {e}")
            return {"success": False, "error": str(e)}