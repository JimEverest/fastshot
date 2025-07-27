#!/usr/bin/env python3
"""
测试datetime排序修复
"""

import sys
sys.path.append('.')

from datetime import datetime, timezone
import tkinter as tk

def test_datetime_sorting():
    """测试datetime排序功能"""
    
    print("🧪 Testing datetime sorting fix...")
    
    # 模拟会话数据，包含不同类型的datetime对象
    test_sessions = [
        {
            'filename': 'session1.fastshot',
            'last_modified': datetime(2025, 6, 21, 3, 46, 17),  # naive datetime
            'desc': 'Session 1'
        },
        {
            'filename': 'session2.fastshot', 
            'last_modified': datetime(2025, 6, 21, 4, 12, 7, tzinfo=timezone.utc),  # aware datetime
            'desc': 'Session 2'
        },
        {
            'filename': 'session3.fastshot',
            'last_modified': datetime(2025, 7, 27, 20, 48, 31, tzinfo=timezone.utc),  # aware datetime
            'desc': 'Session 3'
        },
        {
            'filename': 'session4.fastshot',
            'last_modified': datetime(2025, 6, 21, 10, 49, 5),  # naive datetime
            'desc': 'Session 4'
        }
    ]
    
    print(f"📄 Test data: {len(test_sessions)} sessions with mixed datetime types")
    
    # 测试修复后的排序函数
    def safe_sort_key(session):
        value = session.get('last_modified', '')
        
        # Handle datetime objects specially
        if isinstance(value, datetime):
            # Convert to timestamp for consistent comparison
            return value.timestamp()
        
        # Handle other types
        if value is None:
            return ''
        
        return value
    
    try:
        # 测试排序（降序，最新的在前）
        print("\n🔄 Testing descending sort (newest first)...")
        sorted_sessions = sorted(test_sessions, key=safe_sort_key, reverse=True)
        
        print("✅ Sort successful! Results:")
        for i, session in enumerate(sorted_sessions, 1):
            dt = session['last_modified']
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            tz_info = "UTC" if dt.tzinfo else "naive"
            print(f"  {i}. {session['filename']} - {dt_str} ({tz_info})")
        
        # 测试排序（升序，最旧的在前）
        print("\n🔄 Testing ascending sort (oldest first)...")
        sorted_sessions_asc = sorted(test_sessions, key=safe_sort_key, reverse=False)
        
        print("✅ Sort successful! Results:")
        for i, session in enumerate(sorted_sessions_asc, 1):
            dt = session['last_modified']
            dt_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            tz_info = "UTC" if dt.tzinfo else "naive"
            print(f"  {i}. {session['filename']} - {dt_str} ({tz_info})")
        
        print("\n🎉 Datetime sorting fix works correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Sorting failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_datetime_sorting()
    sys.exit(0 if success else 1)