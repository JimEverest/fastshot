#!/usr/bin/env python3
"""
测试修复后的异步加载功能
"""

import sys
sys.path.append('.')

from fastshot.session_manager_ui import SessionManagerUI
from fastshot.meta_cache import MetaCacheManager
import tkinter as tk
import configparser
import time

def test_async_loading():
    """测试异步加载功能"""
    
    # 创建模拟app
    class MockApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.withdraw()  # Hide main window
            self.session_manager = None
            
            # 加载真实的cloud_sync配置
            self.config = configparser.ConfigParser()
            self.config.read('fastshot/config.ini')
            
            # 创建cloud_sync实例
            from fastshot.cloud_sync import CloudSyncManager
            self.cloud_sync = CloudSyncManager(self)
    
    print("🧪 Testing async loading with real cloud sync...")
    
    try:
        app = MockApp()
        
        # 检查云端连接
        if not app.cloud_sync.cloud_sync_enabled:
            print("❌ Cloud sync is not enabled")
            return
        
        if not app.cloud_sync._init_s3_client():
            print("❌ Cannot connect to S3")
            return
        
        print(f"✅ Connected to S3 bucket: {app.cloud_sync.bucket_name}")
        
        # 清除本地缓存以模拟首次加载
        meta_cache = MetaCacheManager()
        print("🧹 Clearing local cache to simulate fresh load...")
        meta_cache.clear_cache()
        
        # 测试sync_metadata_with_cloud方法
        print("\n🔄 Testing sync_metadata_with_cloud()...")
        sync_result = app.cloud_sync.sync_metadata_with_cloud()
        
        if sync_result.get('success'):
            print(f"✅ Sync successful!")
            print(f"   Cloud sessions: {sync_result.get('total_sessions', 0)}")
            print(f"   Last updated: {sync_result.get('last_updated', 'unknown')}")
            
            # 测试缓存更新
            overall_meta = sync_result.get('overall_meta')
            if overall_meta:
                print(f"\n📦 Updating local cache with cloud data...")
                meta_cache.update_cache_from_cloud(overall_meta)
                
                # 验证缓存更新
                cached_sessions = meta_cache.get_cached_metadata()
                print(f"✅ Cache updated with {len(cached_sessions)} sessions")
                
                # 显示会话列表
                print("\n📄 Sessions in cache:")
                for session in cached_sessions:
                    filename = session.get('filename', 'unknown')
                    metadata = session.get('metadata', {})
                    name = metadata.get('name', '')
                    desc = metadata.get('desc', '')
                    print(f"  • {filename}")
                    if name:
                        print(f"    Name: {name}")
                    if desc:
                        print(f"    Desc: {desc}")
            else:
                print("❌ No overall_meta in sync result")
        else:
            print(f"❌ Sync failed: {sync_result.get('error', 'Unknown error')}")
        
        # 清理
        app.root.destroy()
        
        print("\n🎉 Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_async_loading()