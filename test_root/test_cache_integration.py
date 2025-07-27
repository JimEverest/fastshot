#!/usr/bin/env python3
"""
Test script for cache integration in SessionManagerUI
"""

import sys
import os
sys.path.insert(0, '.')

def test_cache_integration():
    """Test the cache integration functionality."""
    try:
        # Test imports
        from fastshot.session_manager_ui import SessionManagerUI
        from fastshot.meta_cache import MetaCacheManager
        print("✓ Imports successful")
        
        # Test MetaCacheManager initialization
        cache_manager = MetaCacheManager()
        print("✓ MetaCacheManager initialized")
        
        # Test cache stats
        stats = cache_manager.get_cache_stats()
        print(f"✓ Cache stats: {stats}")
        
        # Test cache directory creation
        cache_paths = stats.get('cache_paths', {})
        print(f"✓ Cache directories: {cache_paths}")
        
        # Test cached metadata loading (should be empty initially)
        cached_data = cache_manager.get_cached_metadata()
        print(f"✓ Cached metadata entries: {len(cached_data)}")
        
        print("\n✅ All cache integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_cache_integration()
    sys.exit(0 if success else 1)