# fastshot/cloud_sync.py

import boto3
import json
import os
import base64
from datetime import datetime
from pathlib import Path
import configparser
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
import requests
from urllib.parse import urlparse
import threading
import hashlib
from PIL import Image
import io

class CloudSyncManager:
    """Manages cloud synchronization with AWS S3, encryption, and proxy support."""
    
    def __init__(self, app):
        self.app = app
        self.config = app.config
        self.local_sessions_dir = Path.home() / "fastshot_sessions"
        self.local_sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # S3 client will be initialized when needed
        self.s3_client = None
        self.bucket_name = None
        self.encryption_key = None
        self.proxy_config = None
        
        # Cache for connection testing
        self._connection_tested = False
        self._connection_valid = False
        
        self._load_cloud_config()
    
    def _load_cloud_config(self):
        """Load cloud sync configuration from config file."""
        try:
            # Reset S3 client when config changes
            self._reset_s3_client()
            
            # Check if CloudSync section exists
            if not self.config.has_section('CloudSync'):
                print("CloudSync section not found in config, using defaults")
                self._set_default_config()
                return
            
            # AWS S3 Configuration - with credential cleaning
            self.aws_access_key = self._clean_credential(self.config.get('CloudSync', 'aws_access_key', fallback=''))
            self.aws_secret_key = self._clean_credential(self.config.get('CloudSync', 'aws_secret_key', fallback=''))
            self.aws_region = self.config.get('CloudSync', 'aws_region', fallback='us-east-1').strip()
            self.bucket_name = self.config.get('CloudSync', 's3_bucket_name', fallback='').strip()
            
            # Encryption Configuration
            self.encryption_key = self.config.get('CloudSync', 'encryption_key', fallback='').strip()
            
            # Proxy Configuration
            self.proxy_enabled = self.config.getboolean('CloudSync', 'proxy_enabled', fallback=False)
            self.proxy_url = self.config.get('CloudSync', 'proxy_url', fallback='').strip()
            
            # Cloud sync enabled
            self.cloud_sync_enabled = self.config.getboolean('CloudSync', 'cloud_sync_enabled', fallback=False)
            
            # Validate credentials
            self._validate_credentials()
            
            print(f"DEBUG: Loaded AWS config - Access Key: {'***' if self.aws_access_key else 'EMPTY'} (len: {len(self.aws_access_key)}), "
                  f"Secret Key: {'***' if self.aws_secret_key else 'EMPTY'} (len: {len(self.aws_secret_key)}), "
                  f"Bucket: {self.bucket_name or 'EMPTY'}, "
                  f"Region: {self.aws_region}, "
                  f"Enabled: {self.cloud_sync_enabled}")
            
        except Exception as e:
            print(f"Error loading cloud config: {e}")
            self._set_default_config()
    
    def _reset_s3_client(self):
        """Reset the S3 client to force recreation on next use."""
        self.s3_client = None
        self._connection_tested = False
        self._connection_valid = False
        print("DEBUG: S3 client reset")
    
    def _clean_credential(self, credential):
        """Clean AWS credentials by removing whitespace and potential formatting issues."""
        if not credential:
            return ''
        
        # Remove all whitespace characters (spaces, tabs, newlines)
        cleaned = ''.join(credential.split())
        
        # Remove any potential quotes that might have been added
        cleaned = cleaned.strip('\'"')
        
        return cleaned
    
    def _validate_credentials(self):
        """Validate AWS credentials format."""
        if self.aws_access_key:
            # AWS Access Key should be 20 characters
            if len(self.aws_access_key) != 20:
                print(f"WARNING: AWS Access Key length is {len(self.aws_access_key)}, expected 20")
            
            # Should start with 'AKIA' for standard access keys
            if not self.aws_access_key.startswith(('AKIA', 'ASIA')):
                print(f"WARNING: AWS Access Key doesn't start with expected prefix (AKIA/ASIA)")
        
        if self.aws_secret_key:
            # AWS Secret Key should be 40 characters
            if len(self.aws_secret_key) != 40:
                print(f"WARNING: AWS Secret Key length is {len(self.aws_secret_key)}, expected 40")
            
            # Should only contain alphanumeric characters, +, /, and =
            import re
            if not re.match(r'^[A-Za-z0-9+/=]+$', self.aws_secret_key):
                print(f"WARNING: AWS Secret Key contains invalid characters")
                # Show first and last few characters for debugging
                if len(self.aws_secret_key) > 8:
                    print(f"DEBUG: Secret Key preview: {self.aws_secret_key[:4]}...{self.aws_secret_key[-4:]}")
    
    def _set_default_config(self):
        """Set default configuration values."""
        self.aws_access_key = ''
        self.aws_secret_key = ''
        self.aws_region = 'us-east-1'
        self.bucket_name = ''
        self.encryption_key = ''
        self.proxy_enabled = False
        self.proxy_url = ''
        self.cloud_sync_enabled = False
    
    def _init_s3_client(self):
        """Initialize S3 client with proxy support if needed."""
        # Check if client already exists and is valid
        if self.s3_client is not None:
            try:
                # Test if the existing client is still valid by checking our region
                self.s3_client.meta.region_name
                return True
            except:
                # Client is invalid, will recreate
                self.s3_client = None
        
        try:
            print(f"DEBUG: Initializing S3 client - Access Key: {'***' if self.aws_access_key else 'EMPTY'}, "
                  f"Secret Key: {'***' if self.aws_secret_key else 'EMPTY'}, "
                  f"Bucket: {self.bucket_name or 'EMPTY'}")
            
            if not all([self.aws_access_key, self.aws_secret_key, self.bucket_name]):
                missing = []
                if not self.aws_access_key:
                    missing.append("AWS Access Key")
                if not self.aws_secret_key:
                    missing.append("AWS Secret Key")
                if not self.bucket_name:
                    missing.append("S3 Bucket Name")
                print(f"Missing configuration: {', '.join(missing)}")
                return False
            
            # Configure proxy if enabled
            config_kwargs = {'region_name': self.aws_region}
            
            if self.proxy_enabled and self.proxy_url:
                parsed_proxy = urlparse(self.proxy_url)
                proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                config_kwargs['proxies'] = proxies
                print(f"DEBUG: Using proxy: {self.proxy_url}")
            
            print(f"DEBUG: Creating S3 client for region: {self.aws_region}")
            
            # Create S3 client
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                config=Config(**config_kwargs)
            )
            
            print("DEBUG: S3 client created successfully")
            return True
            
        except Exception as e:
            print(f"Error initializing S3 client: {e}")
            self.s3_client = None
            return False
    
    def _encrypt_data(self, data):
        """Encrypt data using XOR encryption (similar to hyder.py)."""
        if not self.encryption_key:
            return data
        
        key_bytes = self.encryption_key.encode()
        key_len = len(key_bytes)
        encrypted = bytearray()
        
        for i, byte in enumerate(data):
            encrypted.append(byte ^ key_bytes[i % key_len])
        
        return bytes(encrypted)
    
    def _decrypt_data(self, data):
        """Decrypt data using XOR decryption."""
        return self._encrypt_data(data)  # XOR is symmetric
    
    def _disguise_in_image(self, data, image_path=None):
        """Hide encrypted data in an image file (similar to hyder.py)."""
        try:
            # Use default image if none provided
            if not image_path:
                # Create a simple default image
                img = Image.new('RGB', (100, 100), color='white')
            else:
                img = Image.open(image_path)
            
            # Convert image to bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()
            
            # Add marker and encrypted data
            marker = b'FHDR'
            disguised_data = img_bytes + marker + data
            
            return disguised_data
            
        except Exception as e:
            print(f"Error disguising data in image: {e}")
            return data
    
    def _extract_from_image(self, disguised_data):
        """Extract encrypted data from disguised image."""
        try:
            marker = b'FHDR'
            marker_index = disguised_data.find(marker)
            
            if marker_index == -1:
                # No marker found, assume it's regular data
                return disguised_data
            
            # Extract the hidden data after marker
            hidden_data = disguised_data[marker_index + len(marker):]
            return hidden_data
            
        except Exception as e:
            print(f"Error extracting data from image: {e}")
            return disguised_data
    
    def save_session_to_cloud(self, session_data, metadata):
        """Save session to cloud with encryption and image disguise."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            # Generate filename with metadata
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            name = metadata.get('name', '')
            if name.strip():
                # Use name for filename (already sanitized in dialog)
                safe_name = name[:30]  # Limit length
                filename = f"{timestamp}_{safe_name}.fastshot"
            else:
                # Fallback to description or default
                safe_desc = "".join(c for c in metadata.get('desc', '') if c.isalnum() or c in (' ', '-', '_'))[:30]
                safe_desc = safe_desc.replace(' ', '_') if safe_desc else 'session'
                filename = f"{timestamp}_{safe_desc}.fastshot"
            
            # Create thumbnail collage for cloud storage
            from .session_manager import SessionManager
            temp_manager = SessionManager(self)  # Pass self as app for cloud context
            thumbnail_collage = temp_manager._create_session_thumbnail(session_data)
            thumbnail_data = None
            if thumbnail_collage:
                thumbnail_data = temp_manager.serialize_image(thumbnail_collage)
            
                            # Prepare session data with enhanced metadata
                full_session_data = {
                    'session': session_data,
                    'metadata': {
                        'name': metadata.get('name', ''),
                        'desc': metadata.get('desc', ''),
                        'tags': metadata.get('tags', []),
                        'color': metadata.get('color', 'blue'),
                        'class': metadata.get('class', ''),
                        'created_at': datetime.now().isoformat(),
                        'filename': filename,
                        'image_count': len(session_data.get('windows', [])),
                        'thumbnail_collage': thumbnail_data
                    }
                }
            
            # Convert to JSON
            json_data = json.dumps(full_session_data, indent=2, ensure_ascii=False).encode('utf-8')
            
            # Encrypt data
            encrypted_data = self._encrypt_data(json_data)
            
            # Disguise in image
            disguised_data = self._disguise_in_image(encrypted_data)
            
            # Upload to S3
            s3_key = f"sessions/{filename}"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=disguised_data,
                ContentType='image/png'
            )
            
            # Also save locally
            local_path = self.local_sessions_dir / filename
            with open(local_path, 'wb') as f:
                f.write(disguised_data)
            
            print(f"Session saved to cloud: {s3_key}")
            return filename
            
        except Exception as e:
            print(f"Error saving session to cloud: {e}")
            return False
    
    def load_session_from_cloud(self, filename):
        """Load session from cloud with decryption."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            s3_key = f"sessions/{filename}"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            disguised_data = response['Body'].read()
            
            # Extract hidden data
            encrypted_data = self._extract_from_image(disguised_data)
            
            # Decrypt data
            decrypted_data = self._decrypt_data(encrypted_data)
            
            # Parse JSON
            session_data = json.loads(decrypted_data.decode('utf-8'))
            
            return session_data
            
        except Exception as e:
            print(f"Error loading session from cloud: {e}")
            return None
    
    def list_cloud_sessions(self):
        """List all sessions in cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return []
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='sessions/'
            )
            
            sessions = []
            for obj in response.get('Contents', []):
                filename = obj['Key'].replace('sessions/', '')
                if filename.endswith('.fastshot'):
                    sessions.append({
                        'filename': filename,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'source': 'cloud'
                    })
            
            return sessions
            
        except Exception as e:
            print(f"Error listing cloud sessions: {e}")
            return []
    
    def list_local_sessions(self):
        """List all local sessions."""
        try:
            sessions = []
            for file_path in self.local_sessions_dir.glob("*.fastshot"):
                stat = file_path.stat()
                sessions.append({
                    'filename': file_path.name,
                    'size': stat.st_size,
                    'last_modified': datetime.fromtimestamp(stat.st_mtime),
                    'source': 'local',
                    'path': str(file_path)
                })
            
            return sessions
            
        except Exception as e:
            print(f"Error listing local sessions: {e}")
            return []
    
    def sync_to_cloud(self, filename):
        """Sync a local session to cloud."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            local_path = self.local_sessions_dir / filename
            if not local_path.exists():
                print(f"Local file not found: {filename}")
                return False
            
            # Read local file
            with open(local_path, 'rb') as f:
                data = f.read()
            
            # Upload to S3
            s3_key = f"sessions/{filename}"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=data,
                ContentType='image/png'
            )
            
            print(f"Synced to cloud: {filename}")
            return True
            
        except Exception as e:
            print(f"Error syncing to cloud: {e}")
            return False
    
    def sync_from_cloud(self, filename):
        """Sync a cloud session to local."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            s3_key = f"sessions/{filename}"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            data = response['Body'].read()
            
            # Save locally
            local_path = self.local_sessions_dir / filename
            with open(local_path, 'wb') as f:
                f.write(data)
            
            print(f"Synced from cloud: {filename}")
            return True
            
        except Exception as e:
            print(f"Error syncing from cloud: {e}")
            return False
    
    def delete_cloud_session(self, filename):
        """Delete a session from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            s3_key = f"sessions/{filename}"
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            
            print(f"Deleted from cloud: {filename}")
            return True
            
        except Exception as e:
            print(f"Error deleting from cloud: {e}")
            return False
    
    def delete_local_session(self, filename):
        """Delete a local session file."""
        try:
            local_path = self.local_sessions_dir / filename
            if local_path.exists():
                local_path.unlink()
                print(f"Deleted local file: {filename}")
                return True
            return False
            
        except Exception as e:
            print(f"Error deleting local file: {e}")
            return False
    
    def test_connection(self):
        """Test cloud connection with detailed error reporting."""
        try:
            if not self._init_s3_client():
                return False, "Failed to initialize S3 client"
            
            print(f"DEBUG: Testing connection to bucket: {self.bucket_name} in region: {self.aws_region}")
            
            # First try to check if we can access AWS at all
            try:
                sts_client = boto3.client(
                    'sts',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.aws_region
                )
                identity = sts_client.get_caller_identity()
                print(f"DEBUG: AWS credentials valid, Account: {identity.get('Account', 'Unknown')}")
            except Exception as sts_error:
                return False, f"AWS credentials invalid: {str(sts_error)}"
            
            # Test bucket access
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                return True, "Connection successful"
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                
                if error_code == '403':
                    # Try to get more specific information about the 403 error
                    try:
                        # Try to list buckets to see if credentials work at all
                        self.s3_client.list_buckets()
                        return False, f"Bucket '{self.bucket_name}' exists but access denied. Check bucket permissions and region (current: {self.aws_region})"
                    except ClientError as list_error:
                        if list_error.response['Error']['Code'] == '403':
                            return False, f"AWS credentials lack necessary permissions. Error: {error_message}"
                        else:
                            return False, f"AWS credentials issue: {list_error.response['Error']['Message']}"
                elif error_code == '404':
                    return False, f"Bucket '{self.bucket_name}' not found in region '{self.aws_region}'. Check bucket name and region."
                elif error_code == 'NoSuchBucket':
                    return False, f"Bucket '{self.bucket_name}' does not exist. Please create it first."
                else:
                    return False, f"AWS Error ({error_code}): {error_message}"
                    
        except NoCredentialsError:
            return False, "AWS credentials not found or invalid"
        except Exception as e:
            return False, f"Connection error: {str(e)}" 