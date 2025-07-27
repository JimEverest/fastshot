"""
Async Operations Manager - Handles background operations for cloud sync optimization.

This module provides asynchronous operation management for metadata synchronization,
progress tracking, and UI update mechanisms to ensure non-blocking user experience.
"""

import threading
import queue
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AsyncOperationManager:
    """Manages asynchronous background operations with progress tracking."""
    
    def __init__(self):
        """Initialize the async operation manager."""
        self.operations = {}  # operation_id -> operation_info
        self.operation_counter = 0
        self.operation_lock = threading.Lock()
        
        # Progress callback registry
        self.progress_callbacks = {}  # operation_id -> callback_function
        
        # Worker thread pool
        self.worker_threads = []
        self.task_queue = queue.Queue()
        self.shutdown_event = threading.Event()
        
        # Start worker threads
        self._start_worker_threads()
    
    def _start_worker_threads(self, num_workers=3):
        """Start worker threads for background operations."""
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_thread,
                name=f"AsyncWorker-{i}",
                daemon=True
            )
            worker.start()
            self.worker_threads.append(worker)
        
        logger.info(f"Started {num_workers} async worker threads")
    
    def _worker_thread(self):
        """Worker thread that processes background tasks."""
        while not self.shutdown_event.is_set():
            try:
                # Get task from queue with timeout
                task = self.task_queue.get(timeout=1.0)
                if task is None:  # Shutdown signal
                    break
                
                operation_id, func, args, kwargs = task
                
                try:
                    # Update operation status
                    self._update_operation_status(operation_id, 'running')
                    
                    # Execute the task
                    result = func(*args, **kwargs)
                    
                    # Update operation with result
                    self._update_operation_result(operation_id, result, None)
                    
                except Exception as e:
                    logger.error(f"Error in async operation {operation_id}: {e}")
                    self._update_operation_result(operation_id, None, str(e))
                
                finally:
                    self.task_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker thread error: {e}")
    
    def submit_operation(self, func: Callable, *args, 
                        operation_name: str = None,
                        progress_callback: Callable = None,
                        **kwargs) -> str:
        """
        Submit an operation for background execution.
        
        Args:
            func: Function to execute
            *args: Arguments for the function
            operation_name: Human-readable name for the operation
            progress_callback: Callback function for progress updates
            **kwargs: Keyword arguments for the function
            
        Returns:
            str: Operation ID for tracking
        """
        with self.operation_lock:
            self.operation_counter += 1
            operation_id = f"op_{self.operation_counter}_{int(time.time())}"
        
        # Create operation info
        operation_info = {
            'id': operation_id,
            'name': operation_name or f"Operation {self.operation_counter}",
            'status': 'queued',
            'created_at': datetime.now(),
            'started_at': None,
            'completed_at': None,
            'result': None,
            'error': None,
            'progress': 0.0
        }
        
        self.operations[operation_id] = operation_info
        
        # Register progress callback if provided
        if progress_callback:
            self.progress_callbacks[operation_id] = progress_callback
        
        # Submit task to queue
        self.task_queue.put((operation_id, func, args, kwargs))
        
        logger.info(f"Submitted async operation: {operation_id} - {operation_info['name']}")
        return operation_id
    
    def _update_operation_status(self, operation_id: str, status: str):
        """Update operation status."""
        if operation_id in self.operations:
            self.operations[operation_id]['status'] = status
            if status == 'running' and not self.operations[operation_id]['started_at']:
                self.operations[operation_id]['started_at'] = datetime.now()
    
    def _update_operation_result(self, operation_id: str, result: Any, error: str):
        """Update operation with result or error."""
        if operation_id in self.operations:
            op = self.operations[operation_id]
            op['completed_at'] = datetime.now()
            op['progress'] = 100.0
            
            if error:
                op['status'] = 'failed'
                op['error'] = error
            else:
                op['status'] = 'completed'
                op['result'] = result
            
            # Call progress callback if registered
            if operation_id in self.progress_callbacks:
                try:
                    callback = self.progress_callbacks[operation_id]
                    callback(operation_id, op['progress'], op['status'], result, error)
                except Exception as e:
                    logger.error(f"Error in progress callback for {operation_id}: {e}")
    
    def update_progress(self, operation_id: str, progress: float, message: str = None):
        """
        Update operation progress.
        
        Args:
            operation_id: Operation ID
            progress: Progress percentage (0.0 to 100.0)
            message: Optional progress message
        """
        if operation_id in self.operations:
            self.operations[operation_id]['progress'] = progress
            if message:
                self.operations[operation_id]['message'] = message
            
            # Call progress callback if registered
            if operation_id in self.progress_callbacks:
                try:
                    callback = self.progress_callbacks[operation_id]
                    callback(operation_id, progress, 'running', None, None, message)
                except Exception as e:
                    logger.error(f"Error in progress callback for {operation_id}: {e}")
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict]:
        """Get operation status and info."""
        return self.operations.get(operation_id)
    
    def get_all_operations(self) -> Dict[str, Dict]:
        """Get all operations."""
        return self.operations.copy()
    
    def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel an operation (if it hasn't started yet).
        
        Args:
            operation_id: Operation ID to cancel
            
        Returns:
            bool: True if cancelled, False if already running/completed
        """
        if operation_id in self.operations:
            op = self.operations[operation_id]
            if op['status'] == 'queued':
                op['status'] = 'cancelled'
                op['completed_at'] = datetime.now()
                return True
        return False
    
    def wait_for_operation(self, operation_id: str, timeout: float = None) -> Optional[Dict]:
        """
        Wait for an operation to complete.
        
        Args:
            operation_id: Operation ID to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            Optional[Dict]: Operation result or None if timeout
        """
        start_time = time.time()
        
        while operation_id in self.operations:
            op = self.operations[operation_id]
            if op['status'] in ['completed', 'failed', 'cancelled']:
                return op
            
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            time.sleep(0.1)
        
        return None
    
    def cleanup_completed_operations(self, max_age_hours: int = 24):
        """Clean up old completed operations."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        to_remove = []
        for op_id, op_info in self.operations.items():
            if (op_info['status'] in ['completed', 'failed', 'cancelled'] and
                op_info.get('completed_at') and
                op_info['completed_at'].timestamp() < cutoff_time):
                to_remove.append(op_id)
        
        for op_id in to_remove:
            del self.operations[op_id]
            if op_id in self.progress_callbacks:
                del self.progress_callbacks[op_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old operations")
    
    def optimize_memory_usage(self):
        """Optimize memory usage by cleaning up and compacting data structures."""
        try:
            # Clean up completed operations
            self.cleanup_completed_operations(max_age_hours=1)  # More aggressive cleanup
            
            # Clear large result data from completed operations
            for op_info in self.operations.values():
                if op_info['status'] in ['completed', 'failed']:
                    # Keep only essential info, remove large result data
                    if 'result' in op_info and isinstance(op_info['result'], dict):
                        # Keep only summary info, remove detailed data
                        result = op_info['result']
                        if 'sessions' in result:
                            del result['sessions']  # Remove large session data
                        if 'detailed_results' in result:
                            del result['detailed_results']  # Remove detailed results
            
            # Force garbage collection
            import gc
            gc.collect()
            
            logger.info("Memory optimization completed")
            
        except Exception as e:
            logger.error(f"Error during memory optimization: {e}")
    
    def get_memory_stats(self) -> Dict:
        """Get memory usage statistics."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'active_operations': len([op for op in self.operations.values() if op['status'] == 'running']),
                'total_operations': len(self.operations),
                'queue_size': self.task_queue.qsize()
            }
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {'error': str(e)}
    
    def shutdown(self):
        """Shutdown the async operation manager."""
        logger.info("Shutting down AsyncOperationManager...")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Add shutdown signals to queue for each worker
        for _ in self.worker_threads:
            self.task_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.worker_threads:
            worker.join(timeout=5.0)
        
        logger.info("AsyncOperationManager shutdown complete")


class CloudMetadataSyncOperation:
    """Specialized operation for cloud metadata synchronization."""
    
    def __init__(self, cloud_sync_manager, meta_cache_manager, async_manager):
        """
        Initialize cloud metadata sync operation.
        
        Args:
            cloud_sync_manager: CloudSyncManager instance
            meta_cache_manager: MetaCacheManager instance
            async_manager: AsyncOperationManager instance
        """
        self.cloud_sync = cloud_sync_manager
        self.meta_cache = meta_cache_manager
        self.async_manager = async_manager
    
    def sync_all_metadata(self, progress_callback: Callable = None) -> str:
        """
        Start asynchronous sync of all cloud metadata.
        
        Args:
            progress_callback: Callback for progress updates
            
        Returns:
            str: Operation ID
        """
        return self.async_manager.submit_operation(
            self._sync_all_metadata_impl,
            operation_name="Sync All Cloud Metadata",
            progress_callback=progress_callback
        )
    
    def _sync_all_metadata_impl(self) -> Dict:
        """Implementation of metadata sync operation."""
        try:
            # Get current operation ID from thread local storage or similar
            operation_id = getattr(threading.current_thread(), 'operation_id', None)
            
            # Step 1: List all cloud sessions
            self._update_progress(operation_id, 10.0, "Listing cloud sessions...")
            cloud_sessions = self.cloud_sync.list_cloud_sessions()
            total_sessions = len(cloud_sessions)
            
            if total_sessions == 0:
                return {"success": True, "message": "No cloud sessions found", "sessions_processed": 0}
            
            # Step 2: Load overall metadata file
            self._update_progress(operation_id, 20.0, "Loading overall metadata...")
            overall_meta = self.cloud_sync.load_overall_meta_file()
            
            # Step 3: Process sessions in batches
            processed_sessions = []
            batch_size = 5  # Process 5 sessions at a time
            
            for i in range(0, total_sessions, batch_size):
                batch = cloud_sessions[i:i + batch_size]
                batch_progress = 20.0 + (i / total_sessions) * 70.0
                
                self._update_progress(
                    operation_id, 
                    batch_progress, 
                    f"Processing sessions {i+1}-{min(i+batch_size, total_sessions)} of {total_sessions}..."
                )
                
                # Process batch
                for j, session in enumerate(batch):
                    try:
                        filename = session['filename']
                        
                        # Check if we already have cached metadata
                        cached_meta = self.meta_cache.load_meta_index(filename)
                        if cached_meta:
                            processed_sessions.append(filename)
                            continue
                        
                        # Load metadata index from cloud
                        meta_index = self.cloud_sync.load_meta_index_from_cloud(filename)
                        if meta_index:
                            # Save to local cache
                            self.meta_cache.save_meta_index(filename, meta_index)
                            processed_sessions.append(filename)
                        else:
                            # If no metadata index, create basic one from session info
                            basic_meta = {
                                'name': '',
                                'desc': '',
                                'tags': [],
                                'color': '',
                                'class': '',
                                'image_count': 0,
                                'file_size': session.get('size', 0),
                                'created_at': session.get('last_modified', datetime.now()).isoformat(),
                                'thumbnail_collage': None
                            }
                            self.meta_cache.save_meta_index(filename, basic_meta)
                            processed_sessions.append(filename)
                    
                    except Exception as e:
                        logger.error(f"Error processing session {session.get('filename', 'unknown')}: {e}")
                        continue
            
            # Step 4: Update overall metadata cache
            self._update_progress(operation_id, 90.0, "Updating cache...")
            if overall_meta:
                self.meta_cache.update_cache_from_cloud(overall_meta)
            
            # Step 5: Complete
            self._update_progress(operation_id, 100.0, "Sync completed")
            
            return {
                "success": True,
                "message": f"Successfully synced {len(processed_sessions)} sessions",
                "sessions_processed": len(processed_sessions),
                "total_sessions": total_sessions
            }
            
        except Exception as e:
            logger.error(f"Error in metadata sync operation: {e}")
            return {
                "success": False,
                "error": str(e),
                "sessions_processed": len(processed_sessions) if 'processed_sessions' in locals() else 0
            }
    
    def smart_cache_sync(self, orphan_callback: Callable = None, progress_callback: Callable = None) -> str:
        """
        Start asynchronous smart cache synchronization.
        
        Args:
            orphan_callback: Callback for handling orphaned cache entries
            progress_callback: Callback for progress updates
            
        Returns:
            str: Operation ID
        """
        return self.async_manager.submit_operation(
            self._smart_cache_sync_impl,
            orphan_callback,
            operation_name="Smart Cache Synchronization",
            progress_callback=progress_callback
        )
    
    def _smart_cache_sync_impl(self, orphan_callback: Callable = None) -> Dict:
        """Implementation of smart cache sync operation."""
        try:
            # Get current operation ID from thread local storage or similar
            operation_id = getattr(threading.current_thread(), 'operation_id', None)
            
            # Step 1: Load overall metadata file from cloud
            self._update_progress(operation_id, 10.0, "Loading overall metadata from cloud...")
            overall_meta = self.cloud_sync.load_overall_meta_file()
            
            if not overall_meta:
                return {"success": False, "error": "Could not load overall metadata from cloud"}
            
            # Step 2: Perform smart cache synchronization
            self._update_progress(operation_id, 20.0, "Starting smart cache synchronization...")
            
            def progress_wrapper(progress, message):
                # Map progress from 20-90% range
                mapped_progress = 20.0 + (progress / 100.0) * 70.0
                self._update_progress(operation_id, mapped_progress, message)
            
            sync_results = self.meta_cache.smart_sync_with_cloud(
                overall_meta, 
                self.cloud_sync,
                orphan_callback=orphan_callback,
                progress_callback=progress_wrapper
            )
            
            # Step 3: Complete
            self._update_progress(operation_id, 100.0, "Smart cache synchronization completed")
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error in smart cache sync operation: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup_cache(self, progress_callback: Callable = None) -> str:
        """
        Start asynchronous cache cleanup and validation.
        
        Args:
            progress_callback: Callback for progress updates
            
        Returns:
            str: Operation ID
        """
        return self.async_manager.submit_operation(
            self._cleanup_cache_impl,
            operation_name="Cache Cleanup and Validation",
            progress_callback=progress_callback
        )
    
    def _cleanup_cache_impl(self) -> Dict:
        """Implementation of cache cleanup operation."""
        try:
            # Get current operation ID from thread local storage or similar
            operation_id = getattr(threading.current_thread(), 'operation_id', None)
            
            # Perform cache cleanup with validation
            def progress_wrapper(progress, message):
                self._update_progress(operation_id, progress, message)
            
            cleanup_results = self.meta_cache.cleanup_cache_with_validation(
                progress_callback=progress_wrapper
            )
            
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error in cache cleanup operation: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_progress(self, operation_id: str, progress: float, message: str):
        """Update operation progress."""
        if operation_id and self.async_manager:
            self.async_manager.update_progress(operation_id, progress, message)


# Global instance
_async_manager = None

def get_async_manager() -> AsyncOperationManager:
    """Get the global async operation manager instance."""
    global _async_manager
    if _async_manager is None:
        _async_manager = AsyncOperationManager()
    return _async_manager

def shutdown_async_manager():
    """Shutdown the global async operation manager."""
    global _async_manager
    if _async_manager:
        _async_manager.shutdown()
        _async_manager = None