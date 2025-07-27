#!/usr/bin/env python3
"""
Test script for async implementation in SessionManagerUI
"""

import sys
import os
import tkinter as tk
import time
sys.path.insert(0, '.')

def test_async_implementation():
    """Test the async implementation functionality."""
    try:
        print("Testing async implementation...")
        
        # Test async operations module
        from fastshot.async_operations import AsyncOperationManager, get_async_manager
        print("✓ AsyncOperationManager imported successfully")
        
        # Test async manager initialization
        async_manager = get_async_manager()
        print("✓ AsyncOperationManager initialized")
        
        # Test operation submission
        def test_operation():
            time.sleep(1)
            return {"result": "test completed"}
        
        operation_id = async_manager.submit_operation(
            test_operation,
            operation_name="Test Operation"
        )
        print(f"✓ Operation submitted: {operation_id}")
        
        # Wait for completion
        result = async_manager.wait_for_operation(operation_id, timeout=5.0)
        if result and result['status'] == 'completed':
            print("✓ Async operation completed successfully")
        else:
            print("❌ Async operation failed or timed out")
            return False
        
        # Test SessionManagerUI with async
        print("\nTesting SessionManagerUI with async...")
        
        # Create a minimal Tkinter root
        root = tk.Tk()
        root.withdraw()
        
        # Mock app object
        class MockApp:
            def __init__(self):
                self.root = root
                self.session_manager = None
                self.cloud_sync = None
        
        app = MockApp()
        
        # Test SessionManagerUI creation
        from fastshot.session_manager_ui import SessionManagerUI
        session_ui = SessionManagerUI(app)
        print("✓ SessionManagerUI created with async support")
        
        # Test async manager integration
        if hasattr(session_ui, 'async_manager') and session_ui.async_manager:
            print("✓ AsyncOperationManager integrated in SessionManagerUI")
        else:
            print("❌ AsyncOperationManager not integrated")
            return False
        
        # Test cloud metadata sync operation
        if hasattr(session_ui, 'cloud_metadata_sync'):
            if session_ui.cloud_metadata_sync:
                print("✓ CloudMetadataSyncOperation available")
            else:
                print("⚠️ CloudMetadataSyncOperation not available (no cloud_sync)")
        
        print("\n✅ All async implementation tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            # Cleanup
            from fastshot.async_operations import shutdown_async_manager
            shutdown_async_manager()
            root.quit()
            root.destroy()
        except:
            pass

if __name__ == "__main__":
    success = test_async_implementation()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}: Async implementation test")
    sys.exit(0 if success else 1)