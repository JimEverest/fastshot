#!/usr/bin/env python3
"""
Session Cache Test Script

This script tests the new session file caching functionality.
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Add fastshot to path
sys.path.insert(0, str(Path(__file__).parent))

# Import required modules
try:
    from fastshot.meta_cache import MetaCacheManager
    from fastshot.cloud_sync import CloudSyncManager
    print("✓ All modules imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


class MockApp:
    """Mock application for testing."""
    
    def __init__(self):
        # Create mock config
        import configparser
        self.config = configparser.ConfigParser()
        
        # Load actual config if available
        config_path = Path("fastshot/config.ini")
        if config_path.exists():
            self.config.read(config_path)
        
        # Initialize cloud sync
        self.cloud_sync = CloudSyncManager(self)
        print("✓ CloudSyncManager initialized")


def test_session_caching():
    """Test session file caching functionality."""
    print("\n" + "="*60)
    print("SESSION CACHE FUNCTIONALITY TEST")
    print("="*60)
    
    # Initialize components
    app = MockApp()
    meta_cache = MetaCacheManager()
    
    print(f"✓ Components initialized")
    print(f"  Sessions cache directory: {meta_cache.sessions_cache_dir}")
    
    # Test 1: Check initial cache state
    print("\n1. Testing initial cache state...")
    cached_sessions = meta_cache.get_cached_session_files()
    print(f"   Initial cached sessions: {len(cached_sessions)}")
    for session in cached_sessions:
        print(f"   - {session}")
    
    # Test 2: Check if specific sessions are cached
    print("\n2. Testing session cache checking...")
    if app.cloud_sync.cloud_sync_enabled:
        cloud_sessions = app.cloud_sync.list_cloud_sessions()
        print(f"   Found {len(cloud_sessions)} cloud sessions")
        
        for session in cloud_sessions[:3]:  # Test first 3 sessions
            filename = session['filename']
            is_cached = meta_cache.is_session_cached(filename)
            print(f"   {filename}: {'CACHED' if is_cached else 'NOT CACHED'}")
            
            if is_cached:
                cache_info = meta_cache.get_session_cache_info(filename)
                if cache_info:
                    size_mb = cache_info['size'] / (1024 * 1024)
                    print(f"     Size: {size_mb:.2f} MB, Cached at: {cache_info['cached_at']}")
    else:
        print("   Cloud sync disabled - skipping cloud session tests")
    
    # Test 3: Load a session and verify caching
    print("\n3. Testing session loading with caching...")
    if app.cloud_sync.cloud_sync_enabled:
        cloud_sessions = app.cloud_sync.list_cloud_sessions()
        if cloud_sessions:
            test_session = cloud_sessions[0]
            filename = test_session['filename']
            
            print(f"   Testing with session: {filename}")
            
            # Check if already cached
            was_cached = meta_cache.is_session_cached(filename)
            print(f"   Initially cached: {was_cached}")
            
            # Load session (should cache if not already cached)
            print("   Loading session from cloud...")
            start_time = time.time()
            session_data = app.cloud_sync.load_session_from_cloud(filename, use_cache=True)
            load_time = time.time() - start_time
            
            if session_data:
                print(f"   ✓ Session loaded successfully in {load_time:.2f}s")
                
                # Check if now cached
                is_now_cached = meta_cache.is_session_cached(filename)
                print(f"   Now cached: {is_now_cached}")
                
                if is_now_cached:
                    cache_info = meta_cache.get_session_cache_info(filename)
                    if cache_info:
                        size_mb = cache_info['size'] / (1024 * 1024)
                        print(f"   Cache info: {size_mb:.2f} MB")
                
                # Test loading from cache (should be faster)
                print("   Loading same session again (should use cache)...")
                start_time = time.time()
                cached_session_data = app.cloud_sync.load_session_from_cloud(filename, use_cache=True)
                cached_load_time = time.time() - start_time
                
                if cached_session_data:
                    print(f"   ✓ Session loaded from cache in {cached_load_time:.3f}s")
                    print(f"   Speed improvement: {load_time/cached_load_time:.1f}x faster")
                else:
                    print("   ✗ Failed to load session from cache")
            else:
                print("   ✗ Failed to load session")
    
    # Test 4: Cache statistics
    print("\n4. Testing cache statistics...")
    cache_stats = meta_cache.get_cache_statistics()
    
    print(f"   Metadata cache size: {cache_stats.get('cache_size_bytes', 0) / (1024*1024):.2f} MB")
    print(f"   Session cache size: {cache_stats.get('session_cache_size_mb', 0):.2f} MB")
    print(f"   Total cache size: {cache_stats.get('total_cache_size_mb', 0):.2f} MB")
    print(f"   Cached session files: {cache_stats.get('cached_session_files', 0)}")
    print(f"   Metadata files: {cache_stats.get('actual_meta_files', 0)}")
    
    # Test 5: Cache management
    print("\n5. Testing cache management...")
    
    # Test cache optimization (dry run)
    print("   Testing cache optimization...")
    optimization_result = meta_cache.optimize_session_cache(max_size_mb=1000, max_age_days=60)
    
    if optimization_result.get('success'):
        print(f"   ✓ Optimization completed:")
        print(f"     Deleted files: {optimization_result.get('deleted_files', 0)}")
        print(f"     Deleted size: {optimization_result.get('deleted_size_mb', 0):.2f} MB")
        print(f"     Remaining files: {optimization_result.get('remaining_files', 0)}")
        print(f"     Remaining size: {optimization_result.get('remaining_size_mb', 0):.2f} MB")
    else:
        print(f"   ⚠ Optimization failed: {optimization_result.get('error', 'Unknown error')}")
    
    # Test 6: Performance comparison
    print("\n6. Testing performance comparison...")
    if app.cloud_sync.cloud_sync_enabled:
        cloud_sessions = app.cloud_sync.list_cloud_sessions()
        if len(cloud_sessions) >= 2:
            # Test with cached session
            cached_session = cloud_sessions[0]['filename']
            if meta_cache.is_session_cached(cached_session):
                print(f"   Testing cached session: {cached_session}")
                start_time = time.time()
                app.cloud_sync.load_session_from_cloud(cached_session, use_cache=True)
                cached_time = time.time() - start_time
                print(f"   Cached load time: {cached_time:.3f}s")
            
            # Test with non-cached session (disable cache)
            uncached_session = cloud_sessions[1]['filename']
            print(f"   Testing uncached session: {uncached_session}")
            start_time = time.time()
            app.cloud_sync.load_session_from_cloud(uncached_session, use_cache=False)
            uncached_time = time.time() - start_time
            print(f"   Uncached load time: {uncached_time:.3f}s")
            
            if 'cached_time' in locals():
                if cached_time > 0:
                    speedup = uncached_time / cached_time
                    print(f"   Cache speedup: {speedup:.1f}x faster")
    
    print("\n" + "="*60)
    print("SESSION CACHE TEST COMPLETED")
    print("="*60)
    
    return True


def main():
    """Main test execution."""
    print("Session Cache Functionality Test")
    print("=" * 60)
    
    try:
        success = test_session_caching()
        print(f"\nTest result: {'SUCCESS' if success else 'FAILED'}")
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()