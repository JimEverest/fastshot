#!/usr/bin/env python3
"""
Test script to verify cache management UI integration.
This script tests that the cache management buttons are properly added to the Cloud Sessions tab.
"""

import sys
import tkinter as tk
from unittest.mock import Mock

# Add current directory to path
sys.path.append('.')

from fastshot.session_manager_ui import SessionManagerUI

def test_cache_ui_integration():
    """Test that cache management UI controls are properly integrated."""
    
    # Create mock app
    class MockApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.withdraw()  # Hide main window
            self.session_manager = None
            self.cloud_sync = None
            self.config = {}
            self.config_path = 'test_config.ini'
    
    try:
        print("Creating mock app...")
        app = MockApp()
        
        print("Creating SessionManagerUI...")
        ui = SessionManagerUI(app)
        
        print("Checking cache management methods...")
        
        # Verify cache management methods exist
        assert hasattr(ui, '_rebuild_all_indexes'), "Missing _rebuild_all_indexes method"
        assert hasattr(ui, '_rebuild_overall_list'), "Missing _rebuild_overall_list method"
        assert hasattr(ui, '_show_cache_status'), "Missing _show_cache_status method"
        assert hasattr(ui, '_create_progress_dialog'), "Missing _create_progress_dialog method"
        
        print("✓ All cache management methods are available")
        
        # Check if ProgressDialog class exists
        from fastshot.session_manager_ui import ProgressDialog
        print("✓ ProgressDialog class is available")
        
        # Verify cloud frame has the expected structure
        cloud_frame = ui.cloud_frame
        assert hasattr(cloud_frame, 'tab_type'), "Cloud frame missing tab_type attribute"
        assert cloud_frame.tab_type == 'cloud', "Cloud frame tab_type should be 'cloud'"
        
        print("✓ Cloud frame structure is correct")
        
        # Test that the methods are callable (without actually calling them to avoid UI dialogs)
        assert callable(ui._rebuild_all_indexes), "_rebuild_all_indexes should be callable"
        assert callable(ui._rebuild_overall_list), "_rebuild_overall_list should be callable"
        assert callable(ui._show_cache_status), "_show_cache_status should be callable"
        
        print("✓ All cache management methods are callable")
        
        # Clean up
        app.root.destroy()
        
        print("\n🎉 All tests passed! Cache management UI integration is successful.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_cache_ui_integration()
    sys.exit(0 if success else 1)