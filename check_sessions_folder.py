#!/usr/bin/env python3
"""
专门检查S3中的sessions文件夹内容
"""

import sys
sys.path.append('.')

from fastshot.cloud_sync import CloudSyncManager
import configparser

def check_sessions_folder():
    """专门检查sessions文件夹"""
    
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
    print(f"📍 Region: {cloud_sync.aws_region}")
    print()
    
    try:
        # 专门列出sessions/文件夹的内容
        print("📁 Checking sessions/ folder specifically:")
        print("=" * 50)
        
        response = cloud_sync.s3_client.list_objects_v2(
            Bucket=cloud_sync.bucket_name,
            Prefix='sessions/',
            Delimiter='/'
        )
        
        if 'Contents' not in response:
            print("📂 sessions/ folder is empty or doesn't exist")
        else:
            print(f"📄 Found {len(response['Contents'])} objects in sessions/ folder:")
            
            for obj in response['Contents']:
                key = obj['Key']
                size = obj['Size']
                modified = obj['LastModified']
                
                # 只显示sessions/下的文件，不包括文件夹本身
                if key != 'sessions/' and key.startswith('sessions/'):
                    filename = key.replace('sessions/', '')
                    print(f"  • {filename}")
                    print(f"    Size: {size:,} bytes")
                    print(f"    Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 如果是.fastshot文件，尝试读取一些基本信息
                    if filename.endswith('.fastshot'):
                        try:
                            # 读取文件的前几个字节来判断是否是加密的
                            response_obj = cloud_sync.s3_client.get_object(
                                Bucket=cloud_sync.bucket_name, 
                                Key=key,
                                Range='bytes=0-100'  # 只读取前100字节
                            )
                            first_bytes = response_obj['Body'].read()
                            
                            # 检查是否是PNG格式（伪装的图片）
                            if first_bytes.startswith(b'\x89PNG'):
                                print(f"    Type: Disguised as PNG image (encrypted)")
                            elif first_bytes.startswith(b'{'):
                                print(f"    Type: JSON format (unencrypted)")
                            else:
                                print(f"    Type: Unknown format")
                                
                        except Exception as e:
                            print(f"    Error reading file: {e}")
                    
                    print()
        
        # 检查是否有CommonPrefixes（子文件夹）
        if 'CommonPrefixes' in response:
            print(f"📁 Found {len(response['CommonPrefixes'])} subfolders in sessions/:")
            for prefix in response['CommonPrefixes']:
                print(f"  • {prefix['Prefix']}")
        
        # 使用cloud_sync的方法来列出会话
        print("\n🔄 Using CloudSyncManager.list_cloud_sessions():")
        print("=" * 50)
        
        sessions = cloud_sync.list_cloud_sessions()
        if sessions:
            print(f"📄 Found {len(sessions)} sessions via CloudSyncManager:")
            for session in sessions:
                print(f"  • {session['filename']}")
                print(f"    Size: {session['size']:,} bytes")
                print(f"    Modified: {session['last_modified']}")
                print(f"    Source: {session['source']}")
                print()
        else:
            print("📂 No sessions found via CloudSyncManager")
            
    except Exception as e:
        print(f"❌ Error checking sessions folder: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_sessions_folder()