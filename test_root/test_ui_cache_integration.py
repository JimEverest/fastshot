#!/usr/bin/env python3
"""
Test script for SessionManagerUI cache integration
"""

import sys
import os
import tkinter as tk
sys.path.insert(0, '.')

def test_session_manager_ui_cache():
    """Test the SessionManagerUI with cache integration."""
    try:
        # Create a minimal Tkinter root (required for UI components)
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        # Mock app object with required attributes
        class MockApp:
            def __init__(self):
                self.root = root
                self.session_manager = None
                self.cloud_sync = None  # No cloud sync for this test
        
        app = MockApp()
        
        # Test SessionManagerUI creation with cache integration
        from fastshot.session_manager_ui import SessionManagerUI
        print("Creating SessionManagerUI...")
        
        # This should not raise an exception and should initialize the cache
        session_ui = SessionManagerUI(app)
        print("✓ SessionManagerUI created successfully")
        
        # Test cache manager initialization
        if hasattr(session_ui, 'meta_cache') and session_ui.meta_cache:
            print("✓ MetaCacheManager initialized in SessionManagerUI")
            
            # Test cache functionality
            stats = session_ui.meta_cache.get_cache_stats()
            print(f"✓ Cache stats accessible: {len(str(stats))} chars")
            
            # Test cached cloud sessions loading (should return empty list)
            cached_sessions = session_ui._load_cached_cloud_sessions()
            print(f"✓ Cached cloud sessions loaded: {len(cached_sessions)} sessions")
            
            # Test datetime parsing helper
            from datetime import datetime
            test_datetime = session_ui._parse_datetime("2025-01-27T10:30:00.000Z")
            print(f"✓ Datetime parsing works: {test_datetime}")
            
        else:
            print("❌ MetaCacheManager not initialized in SessionManagerUI")
            return False
        
        # Test the new cloud session loading method
        cloud_sessions = session_ui._load_cloud_sessions_with_metadata()
        print(f"✓ Cloud sessions loading method works: {len(cloud_sessions)} sessions")
        
        print("\n✅ All SessionManagerUI cache integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            root.quit()
            root.destroy()
        except:
            pass

if __name__ == "__main__":
    success = test_session_manager_ui_cache()
    sys.exit(0 if success else 1)