#!/usr/bin/env python3
"""
测试完整的后台同步修复
"""

import sys
sys.path.append('.')

from fastshot.session_manager_ui import SessionManagerUI
from fastshot.meta_cache import MetaCacheManager
from fastshot.cloud_sync import CloudSyncManager
import tkinter as tk
import configparser
import time

def test_background_sync_fix():
    """测试后台同步修复"""
    
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
            self.cloud_sync = CloudSyncManager(self)
    
    print("🧪 Testing complete background sync fix...")
    
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
        
        # 创建SessionManagerUI实例来测试完整流程
        print("\n🔄 Creating SessionManagerUI...")
        ui = SessionManagerUI(app)
        
        # 清除本地缓存
        print("🧹 Clearing local cache...")
        ui.meta_cache.clear_cache()
        
        # 手动触发后台同步
        print("\n🔄 Starting manual background sync...")
        
        def manual_sync():
            try:
                print("DEBUG: Starting background sync with cloud...")
                
                # 使用修复后的同步逻辑
                if hasattr(ui.cloud_sync, 'sync_metadata_with_cloud'):
                    sync_result = ui.cloud_sync.sync_metadata_with_cloud()
                    
                    if sync_result.get('success', False):
                        print("DEBUG: Background sync completed successfully")
                        
                        # Update local cache with cloud data
                        overall_meta = sync_result.get('overall_meta')
                        if overall_meta and ui.meta_cache:
                            print(f"DEBUG: Updating local cache with {overall_meta.get('total_sessions', 0)} sessions from cloud")
                            ui.meta_cache.update_cache_from_cloud(overall_meta)
                            
                            # Download missing metadata index files
                            sessions_in_cloud = overall_meta.get('sessions', [])
                            print(f"DEBUG: Found {len(sessions_in_cloud)} sessions in cloud overall meta")
                            
                            for session_info in sessions_in_cloud:
                                filename = session_info.get('filename', '')
                                if filename:
                                    print(f"DEBUG: Checking metadata for {filename}")
                                    # Check if we have the metadata index locally
                                    if not ui.meta_cache.load_meta_index(filename):
                                        print(f"DEBUG: Downloading missing metadata for {filename}")
                                        try:
                                            # Try to load metadata index from cloud
                                            meta_index = ui.cloud_sync.load_meta_index_from_cloud(filename)
                                            if meta_index:
                                                # Extract just the metadata part
                                                metadata = meta_index.get('metadata', {})
                                                ui.meta_cache.save_meta_index(filename, metadata)
                                                print(f"DEBUG: Saved metadata index for {filename}")
                                            else:
                                                print(f"DEBUG: No metadata index found in cloud for {filename}")
                                        except Exception as e:
                                            print(f"DEBUG: Failed to download metadata for {filename}: {e}")
                                    else:
                                        print(f"DEBUG: Metadata already exists locally for {filename}")
                        
                        # Test loading cached sessions
                        print("\n📦 Testing cached session loading...")
                        updated_sessions = ui._load_cached_cloud_sessions()
                        print(f"DEBUG: Loaded {len(updated_sessions)} sessions from cache")
                        
                        if updated_sessions:
                            print("\n📄 Sessions loaded:")
                            for session in updated_sessions:
                                print(f"  • {session.get('filename', 'unknown')}")
                                print(f"    Name: {session.get('name', 'N/A')}")
                                print(f"    Desc: {session.get('desc', 'N/A')}")
                        
                    else:
                        print(f"DEBUG: Background sync failed: {sync_result.get('error', 'Unknown error')}")
                else:
                    print("DEBUG: CloudSyncManager does not support metadata sync")
                    
            except Exception as e:
                print(f"Error in background sync: {e}")
                import traceback
                traceback.print_exc()
        
        # 执行同步
        manual_sync()
        
        # 清理
        app.root.destroy()
        
        print("\n🎉 Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_background_sync_fix()