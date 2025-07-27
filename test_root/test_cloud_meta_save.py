#!/usr/bin/env python3
"""
测试云端元数据保存功能
"""

import sys
sys.path.append('.')

from fastshot.cloud_sync import CloudSyncManager
import configparser

def test_cloud_meta_save():
    """测试云端元数据保存"""
    
    # 创建模拟app
    class MockApp:
        def __init__(self):
            self.config = configparser.ConfigParser()
            self.config.read('fastshot/config.ini')
    
    app = MockApp()
    cloud_sync = CloudSyncManager(app)
    
    if not cloud_sync.cloud_sync_enabled:
        print("❌ Cloud sync is not enabled")
        return
    
    if not cloud_sync._init_s3_client():
        print("❌ Cannot connect to S3")
        return
    
    print(f"✅ Connected to S3 bucket: {cloud_sync.bucket_name}")
    
    # 测试保存一个简单的元数据索引
    test_filename = "test_meta_save.fastshot"
    test_metadata = {
        "name": "Test Session",
        "desc": "Testing metadata save",
        "tags": ["test"],
        "color": "blue",
        "class": "test",
        "image_count": 1,
        "file_size": 1024,
        "created_at": "2025-01-27T12:00:00Z"
    }
    
    print("\n🧪 Testing save_meta_index_to_cloud()...")
    try:
        result = cloud_sync.save_meta_index_to_cloud(test_filename, test_metadata)
        if result:
            print("✅ Meta index saved successfully")
        else:
            print("❌ Meta index save returned False")
    except Exception as e:
        print(f"❌ Error saving meta index: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🧪 Testing update_overall_meta_file()...")
    try:
        result = cloud_sync.update_overall_meta_file()
        if result:
            print("✅ Overall meta file updated successfully")
        else:
            print("❌ Overall meta file update returned False")
    except Exception as e:
        print(f"❌ Error updating overall meta file: {e}")
        import traceback
        traceback.print_exc()
    
    # 验证文件是否真的被创建
    print("\n🔍 Verifying files were created...")
    try:
        # 检查meta_indexes文件夹
        response = cloud_sync.s3_client.list_objects_v2(
            Bucket=cloud_sync.bucket_name,
            Prefix='meta_indexes/'
        )
        
        if 'Contents' in response:
            print(f"📁 Found {len(response['Contents'])} files in meta_indexes/:")
            for obj in response['Contents']:
                print(f"  • {obj['Key']} ({obj['Size']} bytes)")
        else:
            print("📂 meta_indexes/ folder is empty")
        
        # 检查overall_meta.json
        try:
            response = cloud_sync.s3_client.head_object(
                Bucket=cloud_sync.bucket_name,
                Key='overall_meta.json'
            )
            print(f"✅ overall_meta.json exists ({response['ContentLength']} bytes)")
        except cloud_sync.s3_client.exceptions.NoSuchKey:
            print("❌ overall_meta.json does not exist")
            
    except Exception as e:
        print(f"❌ Error verifying files: {e}")

if __name__ == "__main__":
    test_cloud_meta_save()