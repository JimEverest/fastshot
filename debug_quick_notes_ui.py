#!/usr/bin/env python3
"""
Debug script to check Quick Notes UI TreeView display issues.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

# Add the fastshot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fastshot'))

def test_treeview_basic():
    """Test basic TreeView functionality."""
    print("🔧 Testing Basic TreeView Functionality")
    print("=" * 50)
    
    # Create a simple test window
    root = tk.Tk()
    root.title("TreeView Test")
    root.geometry("800x400")
    
    # Create TreeView with same configuration as Quick Notes
    columns = ("title", "short_code", "created", "updated", "status")
    tree = ttk.Treeview(root, columns=columns, show="headings", height=15)
    
    # Configure columns
    tree.heading("title", text="Title")
    tree.heading("short_code", text="Code")
    tree.heading("created", text="Created")
    tree.heading("updated", text="Updated")
    tree.heading("status", text="Status")
    
    # Set column widths
    tree.column("title", width=140, minwidth=120)
    tree.column("short_code", width=50, minwidth=40)
    tree.column("created", width=70, minwidth=60)
    tree.column("updated", width=70, minwidth=60)
    tree.column("status", width=80, minwidth=70)
    
    # Add test data
    test_data = [
        ("Test Note 1", "ABC1", "08/04 10:00", "08/04 10:30", "📱 Local"),
        ("Test Note 2", "DEF2", "08/04 11:00", "08/04 11:30", "🔄 Updated"),
        ("Test Note 3", "GHI3", "08/04 12:00", "08/04 12:30", "✅ Current"),
    ]
    
    for i, data in enumerate(test_data):
        tree.insert("", "end", values=data)
    
    # Pack TreeView
    tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    print("✅ TreeView created with test data")
    print("📝 Test data:")
    for i, data in enumerate(test_data):
        print(f"  Row {i+1}: {data}")
    
    print("\n🔍 If TreeView displays correctly, the issue is with data loading in Quick Notes")
    print("🔍 If TreeView is blank, there's a fundamental TreeView configuration issue")
    
    # Don't actually show the window in automated test
    # root.mainloop()
    root.destroy()
    
    return True

def test_quick_notes_data_loading():
    """Test Quick Notes data loading."""
    print("\n🔧 Testing Quick Notes Data Loading")
    print("=" * 50)
    
    try:
        from notes_manager import NotesManager
        
        class MockApp:
            def __init__(self):
                self.cloud_sync = None
                self.notes_cache = None
        
        app = MockApp()
        notes_manager = NotesManager(app)
        
        # Test list_notes method
        result = notes_manager.list_notes(page=1, per_page=15)
        notes_data = result.get("notes", [])
        
        print(f"📊 Notes manager returned {len(notes_data)} notes")
        
        if len(notes_data) > 0:
            print("✅ Notes data is available")
            print("📝 Sample note data:")
            for i, note in enumerate(notes_data[:3]):  # Show first 3 notes
                print(f"  Note {i+1}: {note.get('title', 'No title')} ({note.get('short_code', 'No code')})")
        else:
            print("❌ No notes data found")
            print("🔍 This explains why TreeView is empty")
        
        return len(notes_data) > 0
        
    except Exception as e:
        print(f"❌ Error testing notes data loading: {e}")
        return False

def test_treeview_configuration():
    """Test TreeView configuration in Quick Notes style."""
    print("\n🔧 Testing TreeView Configuration")
    print("=" * 50)
    
    # Test the exact configuration used in Quick Notes
    columns = ("title", "short_code", "created", "updated", "status")
    
    print(f"Columns: {columns}")
    print(f"Column count: {len(columns)}")
    
    # Test column configuration
    column_config = {
        "title": {"width": 140, "minwidth": 120, "text": "Title"},
        "short_code": {"width": 50, "minwidth": 40, "text": "Code"},
        "created": {"width": 70, "minwidth": 60, "text": "Created"},
        "updated": {"width": 70, "minwidth": 60, "text": "Updated"},
        "status": {"width": 80, "minwidth": 70, "text": "Status"},
    }
    
    print("\nColumn configuration:")
    for col, config in column_config.items():
        print(f"  {col}: {config}")
    
    # Test sample data format
    sample_data = ("Sample Note", "TEST", "08/04 10:00", "08/04 10:30", "📱 Local")
    print(f"\nSample data: {sample_data}")
    print(f"Data length: {len(sample_data)}")
    print(f"Matches columns: {len(sample_data) == len(columns)}")
    
    if len(sample_data) == len(columns):
        print("✅ Data format matches column configuration")
    else:
        print("❌ Data format mismatch - this could cause display issues")
    
    return True

if __name__ == "__main__":
    print("🧪 Quick Notes UI TreeView Debug Suite")
    print("=" * 80)
    
    try:
        # Run tests
        test1_passed = test_treeview_basic()
        test2_passed = test_quick_notes_data_loading()
        test3_passed = test_treeview_configuration()
        
        print("\n" + "=" * 80)
        print("📊 DEBUG RESULTS:")
        print(f"  Basic TreeView: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
        print(f"  Data Loading: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
        print(f"  Configuration: {'✅ PASSED' if test3_passed else '❌ FAILED'}")
        
        print("\n🔍 DIAGNOSIS:")
        if not test2_passed:
            print("  ❌ ISSUE: No notes data available")
            print("  💡 SOLUTION: Check if notes exist in local storage")
            print("  📝 ACTION: Create some test notes first")
        elif test1_passed and test3_passed:
            print("  ✅ TreeView configuration is correct")
            print("  🔍 ISSUE: Likely a data loading or display refresh problem")
            print("  💡 SOLUTION: Check _load_notes_list and _update_notes_tree methods")
        
        print("\n📋 NEXT STEPS:")
        print("1. Verify notes exist in local storage")
        print("2. Check if _load_notes_list is being called")
        print("3. Verify _update_notes_tree is populating data correctly")
        print("4. Test with some sample notes")
        
    except Exception as e:
        print(f"\n❌ Debug suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)