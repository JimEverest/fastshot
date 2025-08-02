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
    
    # Notes-specific cloud sync methods
    def save_note_to_cloud(self, note_data: dict) -> bool:
        """
        Save a note to cloud storage.
        
        Args:
            note_data: Note data dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self._ensure_s3_client():
                return False
            
            note_id = note_data.get("id")
            if not note_id:
                print("Error: Note ID is required for cloud sync")
                return False
            
            # Prepare note data for cloud storage
            cloud_note_data = note_data.copy()
            cloud_note_data["cloud_sync_timestamp"] = datetime.now().isoformat()
            
            # Convert to JSON
            note_json = json.dumps(cloud_note_data, indent=2, ensure_ascii=False)
            
            # Encrypt if encryption is enabled
            if self.encryption_key:
                note_json = self._encrypt_data(note_json)
            
            # Upload to S3
            s3_key = f"quicknotes/notes/{note_id}.json"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=note_json,
                ContentType='application/json'
            )
            
            print(f"Note saved to cloud: {note_id}")
            return True
            
        except Exception as e:
            print(f"Error saving note to cloud: {e}")
            return False
    
    def load_note_from_cloud(self, note_id: str) -> dict:
        """
        Load a note from cloud storage.
        
        Args:
            note_id: Note identifier
            
        Returns:
            dict: Note data if found, None otherwise
        """
        try:
            if not self._ensure_s3_client():
                return None
            
            s3_key = f"quicknotes/notes/{note_id}.json"
            
            # Download from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            note_data = response['Body'].read()
            
            # Decrypt if encryption is enabled
            if self.encryption_key:
                note_data = self._decrypt_data(note_data)
            
            # Parse JSON
            note_json = json.loads(note_data)
            
            print(f"Note loaded from cloud: {note_id}")
            return note_json
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"Note not found in cloud: {note_id}")
            else:
                print(f"Error loading note from cloud: {e}")
            return None
        except Exception as e:
            print(f"Error loading note from cloud: {e}")
            return None
    
    def delete_note_from_cloud(self, note_id: str) -> bool:
        """
        Delete a note from cloud storage.
        
        Args:
            note_id: Note identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self._ensure_s3_client():
                return False
            
            s3_key = f"quicknotes/notes/{note_id}.json"
            
            # Delete from S3
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            print(f"Note deleted from cloud: {note_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting note from cloud: {e}")
            return False
    
    def load_notes_overall_index(self) -> dict:
        """
        Load the overall notes index from cloud storage.
        
        Returns:
            dict: Notes index if found, None otherwise
        """
        try:
            if not self._ensure_s3_client():
                return None
            
            s3_key = "quicknotes/overall_notes_index.json"
            
            # Download from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            index_data = response['Body'].read()
            
            # Decrypt if encryption is enabled
            if self.encryption_key:
                index_data = self._decrypt_data(index_data)
            
            # Parse JSON
            index_json = json.loads(index_data)
            
            print("Notes index loaded from cloud")
            return index_json
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print("Notes index not found in cloud, creating empty index")
                return self._create_empty_notes_index()
            else:
                print(f"Error loading notes index from cloud: {e}")
            return None
        except Exception as e:
            print(f"Error loading notes index from cloud: {e}")
            return None
    
    def update_notes_overall_index(self) -> bool:
        """
        Update the overall notes index in cloud storage by scanning all notes.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self._ensure_s3_client():
                return False
            
            # List all notes in cloud
            notes_prefix = "quicknotes/notes/"
            notes_list = []
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=notes_prefix)
            
            total_words = 0
            total_size = 0
            most_recent_update = None
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['Key'].endswith('.json'):
                            try:
                                # Load note metadata
                                note_data = self.load_note_from_cloud(
                                    obj['Key'].replace(notes_prefix, '').replace('.json', '')
                                )
                                
                                if note_data:
                                    # Extract metadata for index
                                    note_info = {
                                        "id": note_data.get("id"),
                                        "title": note_data.get("title"),
                                        "short_code": note_data.get("short_code"),
                                        "created_at": note_data.get("created_at"),
                                        "updated_at": note_data.get("updated_at"),
                                        "file_size": obj['Size'],
                                        "word_count": note_data.get("metadata", {}).get("word_count", 0)
                                    }
                                    
                                    notes_list.append(note_info)
                                    
                                    # Update statistics
                                    total_words += note_info["word_count"]
                                    total_size += note_info["file_size"]
                                    
                                    # Track most recent update
                                    if not most_recent_update or note_info["updated_at"] > most_recent_update:
                                        most_recent_update = note_info["updated_at"]
                                        
                            except Exception as e:
                                print(f"Error processing note {obj['Key']}: {e}")
                                continue
            
            # Create updated index
            index_data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_notes": len(notes_list),
                "notes": notes_list,
                "statistics": {
                    "total_words": total_words,
                    "total_size_bytes": total_size,
                    "most_recent_update": most_recent_update
                }
            }
            
            # Save index to cloud
            return self._save_notes_index_to_cloud(index_data)
            
        except Exception as e:
            print(f"Error updating notes index: {e}")
            return False
    
    def rebuild_notes_index(self) -> dict:
        """
        Rebuild the notes index by downloading all notes from cloud.
        
        Returns:
            dict: Result with success status and statistics
        """
        try:
            print("Starting notes index rebuild...")
            
            if not self._ensure_s3_client():
                return {"success": False, "error": "S3 client not available"}
            
            # This is the same as update_notes_overall_index but with more detailed reporting
            success = self.update_notes_overall_index()
            
            if success:
                # Load the rebuilt index to get statistics
                index_data = self.load_notes_overall_index()
                if index_data:
                    return {
                        "success": True,
                        "total_notes": index_data.get("total_notes", 0),
                        "total_words": index_data.get("statistics", {}).get("total_words", 0),
                        "total_size_bytes": index_data.get("statistics", {}).get("total_size_bytes", 0)
                    }
            
            return {"success": False, "error": "Failed to rebuild index"}
            
        except Exception as e:
            print(f"Error rebuilding notes index: {e}")
            return {"success": False, "error": str(e)}
    
    def get_note_public_url(self, note_id: str, expiration: int = 3600) -> str:
        """
        Generate a public URL for a note.
        
        Args:
            note_id: Note identifier
            expiration: URL expiration time in seconds (default 1 hour)
            
        Returns:
            str: Public URL if successful, None otherwise
        """
        try:
            if not self._ensure_s3_client():
                return None
            
            s3_key = f"quicknotes/notes/{note_id}.json"
            
            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            
            print(f"Generated public URL for note: {note_id}")
            return url
            
        except Exception as e:
            print(f"Error generating public URL for note: {e}")
            return None
    
    def _create_empty_notes_index(self) -> dict:
        """Create an empty notes index structure."""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_notes": 0,
            "notes": [],
            "statistics": {
                "total_words": 0,
                "total_size_bytes": 0,
                "most_recent_update": None
            }
        }
    
    def _save_notes_index_to_cloud(self, index_data: dict) -> bool:
        """
        Save notes index to cloud storage.
        
        Args:
            index_data: Index data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self._ensure_s3_client():
                return False
            
            # Convert to JSON
            index_json = json.dumps(index_data, indent=2, ensure_ascii=False)
            
            # Encrypt if encryption is enabled
            if self.encryption_key:
                index_json = self._encrypt_data(index_json)
            
            # Upload to S3
            s3_key = "quicknotes/overall_notes_index.json"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=index_json,
                ContentType='application/json'
            )
            
            print("Notes index saved to cloud")
            return True
            
        except Exception as e:
            print(f"Error saving notes index to cloud: {e}")
            return False
    
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
            
            # SSL verification settings for proxy environments
            ssl_verify = self.config.getboolean('CloudSync', 'ssl_verify', fallback=True)
            if not ssl_verify:
                print("WARNING: SSL verification disabled - this is not recommended for production use")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            if self.proxy_enabled and self.proxy_url:
                parsed_proxy = urlparse(self.proxy_url)
                proxies = {
                    'http': self.proxy_url,
                    'https': self.proxy_url
                }
                config_kwargs['proxies'] = proxies
                print(f"DEBUG: Using proxy: {self.proxy_url}")
            
            # Simple and effective SSL verification bypass
            if not ssl_verify:
                print("DEBUG: Applying simple SSL verification bypass...")
                
                # Set environment variables to disable SSL verification
                os.environ['CURL_CA_BUNDLE'] = ''
                os.environ['REQUESTS_CA_BUNDLE'] = ''
                os.environ['PYTHONHTTPSVERIFY'] = '0'
                
                # Disable SSL verification globally
                import ssl
                import urllib3
                ssl._create_default_https_context = ssl._create_unverified_context
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                print("DEBUG: SSL verification bypass completed")
            
            print(f"DEBUG: Creating S3 client for region: {self.aws_region}, SSL verify: {ssl_verify}")
            
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
    
    def save_session_to_cloud(self, session_data, metadata, progress_callback=None):
        """Save session to cloud with encryption, metadata creation, and rollback mechanism."""
        saved_files = []  # Track files for rollback
        
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            if progress_callback:
                progress_callback(0, "Initializing save operation...")
            
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
            
            if progress_callback:
                progress_callback(10, "Creating thumbnail collage...")
            
            # Create thumbnail collage for cloud storage
            from .session_manager import SessionManager
            temp_manager = SessionManager(self)  # Pass self as app for cloud context
            thumbnail_collage = temp_manager._create_session_thumbnail(session_data)
            thumbnail_data = None
            if thumbnail_collage:
                thumbnail_data = temp_manager.serialize_image(thumbnail_collage)
            
            if progress_callback:
                progress_callback(20, "Preparing session data...")
            
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
            
            if progress_callback:
                progress_callback(30, "Encrypting session data...")
            
            # Convert to JSON
            json_data = json.dumps(full_session_data, indent=2, ensure_ascii=False).encode('utf-8')
            
            # Encrypt data
            encrypted_data = self._encrypt_data(json_data)
            
            # Disguise in image
            disguised_data = self._disguise_in_image(encrypted_data)
            
            if progress_callback:
                progress_callback(50, "Uploading session file...")
            
            # Upload main session file to S3
            s3_key = f"sessions/{filename}"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=disguised_data,
                ContentType='image/png'
            )
            saved_files.append(s3_key)
            
            if progress_callback:
                progress_callback(70, "Creating metadata index...")
            
            # Create and save metadata index file atomically
            metadata_with_size = metadata.copy()
            metadata_with_size['file_size'] = len(disguised_data)
            metadata_with_size['image_count'] = len(session_data.get('windows', []))
            metadata_with_size['created_at'] = full_session_data['metadata']['created_at']
            
            if not self.save_meta_index_to_cloud(filename, metadata_with_size):
                raise Exception(f"Failed to save metadata index for {filename}")
            
            # Track metadata index file for rollback
            base_name = filename.replace('.fastshot', '')
            meta_filename = f"{base_name}.meta.json"
            meta_s3_key = f"meta_indexes/{meta_filename}"
            saved_files.append(meta_s3_key)
            
            if progress_callback:
                progress_callback(85, "Updating overall metadata...")
            
            # Update overall metadata file atomically
            if not self.update_overall_meta_file():
                raise Exception(f"Failed to update overall metadata file after saving {filename}")
            
            saved_files.append("overall_meta.json")
            
            if progress_callback:
                progress_callback(95, "Saving local copy...")
            
            # Also save locally
            local_path = self.local_sessions_dir / filename
            with open(local_path, 'wb') as f:
                f.write(disguised_data)
            
            if progress_callback:
                progress_callback(100, "Save completed successfully")
            
            print(f"Session saved to cloud: {s3_key}")
            return filename
            
        except Exception as e:
            print(f"Error saving session to cloud: {e}")
            
            if progress_callback:
                progress_callback(-1, f"Save failed: {str(e)}")
            
            # Rollback mechanism - delete any files that were uploaded
            self._rollback_save_operation(saved_files, filename if 'filename' in locals() else None)
            
            return False
    
    def _rollback_save_operation(self, saved_files, filename):
        """Rollback save operation by deleting uploaded files."""
        try:
            if not self.s3_client or not saved_files:
                return
            
            print(f"Rolling back save operation for {filename}, deleting {len(saved_files)} files...")
            
            for s3_key in saved_files:
                try:
                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                    print(f"Rolled back: deleted {s3_key}")
                except Exception as delete_error:
                    print(f"Warning: Could not delete {s3_key} during rollback: {delete_error}")
            
            # Also delete local file if it was created
            if filename:
                local_path = self.local_sessions_dir / filename
                if local_path.exists():
                    try:
                        local_path.unlink()
                        print(f"Rolled back: deleted local file {filename}")
                    except Exception as local_error:
                        print(f"Warning: Could not delete local file during rollback: {local_error}")
            
            print("Rollback completed")
            
        except Exception as e:
            print(f"Error during rollback: {e}")
    
    def load_session_from_cloud(self, filename, use_cache=True):
        """Load session from cloud with decryption and intelligent caching."""
        try:
            # Check local cache first if enabled
            if use_cache:
                local_path = self.local_sessions_dir / filename
                if local_path.exists():
                    print(f"Loading session from local cache: {filename}")
                    try:
                        with open(local_path, 'rb') as f:
                            disguised_data = f.read()
                        
                        # Extract and decrypt cached data
                        encrypted_data = self._extract_from_image(disguised_data)
                        decrypted_data = self._decrypt_data(encrypted_data)
                        session_data = json.loads(decrypted_data.decode('utf-8'))
                        
                        return session_data
                    except Exception as cache_error:
                        print(f"Error loading from cache, will download from cloud: {cache_error}")
                        # Continue to cloud download if cache fails
            
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            print(f"Downloading session from cloud: {filename}")
            s3_key = f"sessions/{filename}"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            disguised_data = response['Body'].read()
            
            # Cache the downloaded data locally if caching is enabled
            if use_cache:
                try:
                    local_path = self.local_sessions_dir / filename
                    with open(local_path, 'wb') as f:
                        f.write(disguised_data)
                    print(f"Cached session locally: {filename}")
                except Exception as cache_error:
                    print(f"Warning: Could not cache session locally: {cache_error}")
            
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
            
            # Delete main session file
            s3_key = f"sessions/{filename}"
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            
            # Delete corresponding metadata index file
            base_name = filename.replace('.fastshot', '')
            meta_filename = f"{base_name}.meta.json"
            meta_s3_key = f"meta_indexes/{meta_filename}"
            
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=meta_s3_key)
                print(f"Deleted metadata index: {meta_s3_key}")
            except Exception as meta_error:
                print(f"Warning: Could not delete metadata index {meta_s3_key}: {meta_error}")
            
            # Update overall metadata file
            if not self.update_overall_meta_file():
                print(f"Warning: Failed to update overall metadata file after deleting {filename}")
            
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
    
    def save_meta_index_to_cloud(self, filename, metadata):
        """Save metadata index file to cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            # Create metadata index structure
            meta_index = {
                "version": "1.0",
                "filename": filename,
                "metadata": {
                    "name": metadata.get('name', ''),
                    "desc": metadata.get('desc', ''),
                    "tags": metadata.get('tags', []),
                    "color": metadata.get('color', 'blue'),
                    "class": metadata.get('class', ''),
                    "image_count": metadata.get('image_count', 0),
                    "created_at": metadata.get('created_at', datetime.now().isoformat()),
                    "file_size": metadata.get('file_size', 0)
                },
                "checksum": self._calculate_checksum(json.dumps(metadata, sort_keys=True)),
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
            
            # Convert to JSON
            json_data = json.dumps(meta_index, indent=2, ensure_ascii=False).encode('utf-8')
            
            # Generate meta index filename
            base_name = filename.replace('.fastshot', '')
            meta_filename = f"{base_name}.meta.json"
            
            # Upload to S3 in meta_indexes folder
            s3_key = f"meta_indexes/{meta_filename}"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            print(f"Metadata index saved to cloud: {s3_key}")
            return True
            
        except Exception as e:
            print(f"Error saving metadata index to cloud: {e}")
            return False
    
    def load_meta_index_from_cloud(self, filename):
        """Load metadata index file from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            # Generate meta index filename
            base_name = filename.replace('.fastshot', '')
            meta_filename = f"{base_name}.meta.json"
            s3_key = f"meta_indexes/{meta_filename}"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = response['Body'].read()
            
            # Parse JSON
            meta_index = json.loads(json_data.decode('utf-8'))
            
            return meta_index
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"Metadata index not found: {filename}")
                return None
            else:
                print(f"Error loading metadata index from cloud: {e}")
                return None
        except Exception as e:
            print(f"Error loading metadata index from cloud: {e}")
            return None
    
    def update_overall_meta_file(self):
        """Update the overall metadata file with current session list."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            # List all sessions in cloud
            cloud_sessions = self.list_cloud_sessions()
            
            # Create overall metadata structure
            overall_meta = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_sessions": len(cloud_sessions),
                "sessions": []
            }
            
            # Add session information
            for session in cloud_sessions:
                session_info = {
                    "filename": session['filename'],
                    "created_at": session['last_modified'].isoformat() if hasattr(session['last_modified'], 'isoformat') else str(session['last_modified']),
                    "file_size": session['size'],
                    "checksum": self._calculate_file_checksum_from_cloud(session['filename'])
                }
                overall_meta['sessions'].append(session_info)
            
            # Calculate overall checksum
            overall_meta['checksum'] = self._calculate_checksum(json.dumps(overall_meta['sessions'], sort_keys=True))
            
            # Convert to JSON
            json_data = json.dumps(overall_meta, indent=2, ensure_ascii=False).encode('utf-8')
            
            # Upload to S3
            s3_key = "overall_meta.json"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            print(f"Overall metadata file updated with {len(cloud_sessions)} sessions")
            return True
            
        except Exception as e:
            print(f"Error updating overall metadata file: {e}")
            return False
    
    def load_overall_meta_file(self):
        """Load the overall metadata file from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            s3_key = "overall_meta.json"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = response['Body'].read()
            
            # Parse JSON
            overall_meta = json.loads(json_data.decode('utf-8'))
            
            print(f"Loaded overall metadata file with {overall_meta.get('total_sessions', 0)} sessions")
            return overall_meta
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print("Overall metadata file not found in cloud")
                return None
            else:
                print(f"Error loading overall metadata file from cloud: {e}")
                return None
        except Exception as e:
            print(f"Error loading overall metadata file from cloud: {e}")
            return None
    
    def sync_metadata_with_cloud(self):
        """Synchronize metadata using filename-based comparison for immutable sessions."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return {"success": False, "error": "Cloud sync not available"}
            
            # Load overall metadata file from cloud
            overall_meta = self.load_overall_meta_file()
            if not overall_meta:
                return {"success": False, "error": "Could not load overall metadata file"}
            
            # Get cloud session filenames from overall metadata
            cloud_filenames = set(session['filename'] for session in overall_meta.get('sessions', []))
            
            sync_result = {
                "success": True,
                "cloud_filenames": list(cloud_filenames),
                "overall_meta": overall_meta,
                "last_updated": overall_meta.get('last_updated'),
                "total_sessions": overall_meta.get('total_sessions', 0)
            }
            
            return sync_result
            
        except Exception as e:
            print(f"Error synchronizing metadata with cloud: {e}")
            return {"success": False, "error": str(e)}
    
    def load_overall_meta_file(self):
        """Load the overall metadata file from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            s3_key = "overall_meta.json"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = response['Body'].read()
            
            # Parse JSON
            overall_meta = json.loads(json_data.decode('utf-8'))
            
            return overall_meta
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"Overall metadata file not found in cloud")
                return None
            else:
                print(f"Error loading overall metadata from cloud: {e}")
                return None
        except Exception as e:
            print(f"Error loading overall metadata from cloud: {e}")
            return None
    
    def rebuild_all_meta_indexes(self, progress_callback=None):
        """Rebuild all metadata indexes by downloading and processing all sessions."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return {"success": False, "error": "Cloud sync not available"}
            
            if progress_callback:
                progress_callback(0, "Starting metadata index rebuild...")
            
            # Get list of all cloud sessions
            cloud_sessions = self.list_cloud_sessions()
            total_sessions = len(cloud_sessions)
            
            if total_sessions == 0:
                return {"success": True, "message": "No cloud sessions found", "rebuilt_count": 0}
            
            rebuilt_count = 0
            errors = []
            
            for i, session in enumerate(cloud_sessions):
                try:
                    filename = session['filename']
                    progress = (i / total_sessions) * 90
                    
                    if progress_callback:
                        progress_callback(progress, f"Processing {filename} ({i+1}/{total_sessions})...")
                    
                    # Load full session to extract metadata
                    session_data = self.load_session_from_cloud(filename)
                    if session_data and 'metadata' in session_data:
                        metadata = session_data['metadata']
                        
                        # Ensure required fields
                        metadata.setdefault('file_size', session.get('size', 0))
                        metadata.setdefault('created_at', session.get('last_modified', datetime.now()).isoformat())
                        
                        # Save metadata index to cloud
                        if self.save_meta_index_to_cloud(filename, metadata):
                            rebuilt_count += 1
                        else:
                            errors.append(f"Failed to save metadata index for {filename}")
                    else:
                        # Create basic metadata if session data is incomplete
                        basic_metadata = {
                            'name': filename.replace('.fastshot', ''),
                            'desc': 'Rebuilt metadata',
                            'tags': [],
                            'color': 'blue',
                            'class': '',
                            'image_count': 0,
                            'file_size': session.get('size', 0),
                            'created_at': session.get('last_modified', datetime.now()).isoformat(),
                            'thumbnail_collage': None
                        }
                        
                        if self.save_meta_index_to_cloud(filename, basic_metadata):
                            rebuilt_count += 1
                        else:
                            errors.append(f"Failed to save basic metadata index for {filename}")
                
                except Exception as e:
                    error_msg = f"Error processing {filename}: {e}"
                    print(error_msg)
                    errors.append(error_msg)
            
            # Update overall metadata file
            if progress_callback:
                progress_callback(90, "Updating overall metadata file...")
            
            if not self.update_overall_meta_file():
                errors.append("Failed to update overall metadata file")
            
            if progress_callback:
                progress_callback(100, "Metadata index rebuild completed")
            
            result = {
                "success": True,
                "rebuilt_count": rebuilt_count,
                "total_sessions": total_sessions,
                "errors": errors
            }
            
            print(f"Metadata index rebuild completed: {rebuilt_count}/{total_sessions} successful")
            return result
            
        except Exception as e:
            error_msg = f"Error during metadata index rebuild: {e}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def verify_cloud_integrity(self, progress_callback=None):
        """Verify integrity of cloud storage structure and metadata."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return {"success": False, "error": "Cloud sync not available"}
            
            if progress_callback:
                progress_callback(0, "Starting cloud integrity verification...")
            
            integrity_results = {
                "success": True,
                "sessions_checked": 0,
                "metadata_indexes_checked": 0,
                "missing_metadata_indexes": [],
                "corrupted_sessions": [],
                "orphaned_metadata": [],
                "overall_meta_valid": False,
                "errors": []
            }
            
            # Check overall metadata file
            if progress_callback:
                progress_callback(10, "Checking overall metadata file...")
            
            overall_meta = self.load_overall_meta_file()
            if overall_meta:
                integrity_results["overall_meta_valid"] = True
                expected_sessions = set(s.get('filename', '') for s in overall_meta.get('sessions', []))
            else:
                integrity_results["errors"].append("Overall metadata file missing or corrupted")
                expected_sessions = set()
            
            # List actual sessions in cloud
            if progress_callback:
                progress_callback(20, "Listing cloud sessions...")
            
            cloud_sessions = self.list_cloud_sessions()
            actual_sessions = set(s['filename'] for s in cloud_sessions)
            integrity_results["sessions_checked"] = len(actual_sessions)
            
            # List metadata indexes
            if progress_callback:
                progress_callback(30, "Listing metadata indexes...")
            
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix='meta_indexes/'
                )
                
                metadata_indexes = set()
                for obj in response.get('Contents', []):
                    meta_filename = obj['Key'].replace('meta_indexes/', '')
                    if meta_filename.endswith('.meta.json'):
                        # Convert back to session filename
                        base_name = meta_filename.replace('.meta.json', '')
                        session_filename = f"{base_name}.fastshot"
                        metadata_indexes.add(session_filename)
                
                integrity_results["metadata_indexes_checked"] = len(metadata_indexes)
                
            except Exception as e:
                integrity_results["errors"].append(f"Error listing metadata indexes: {e}")
                metadata_indexes = set()
            
            # Find missing metadata indexes
            missing_metadata = actual_sessions - metadata_indexes
            integrity_results["missing_metadata_indexes"] = list(missing_metadata)
            
            # Find orphaned metadata indexes
            orphaned_metadata = metadata_indexes - actual_sessions
            integrity_results["orphaned_metadata"] = list(orphaned_metadata)
            
            # Verify session integrity (sample check)
            if progress_callback:
                progress_callback(50, "Verifying session integrity...")
            
            sample_sessions = list(actual_sessions)[:min(5, len(actual_sessions))]  # Check up to 5 sessions
            for i, filename in enumerate(sample_sessions):
                try:
                    progress = 50 + (i / len(sample_sessions)) * 30
                    if progress_callback:
                        progress_callback(progress, f"Checking session {filename}...")
                    
                    session_data = self.load_session_from_cloud(filename)
                    if not session_data:
                        integrity_results["corrupted_sessions"].append(filename)
                
                except Exception as e:
                    integrity_results["corrupted_sessions"].append(filename)
                    integrity_results["errors"].append(f"Error checking {filename}: {e}")
            
            if progress_callback:
                progress_callback(100, "Cloud integrity verification completed")
            
            print(f"Cloud integrity check: {len(missing_metadata)} missing metadata, "
                  f"{len(orphaned_metadata)} orphaned metadata, "
                  f"{len(integrity_results['corrupted_sessions'])} corrupted sessions")
            
            return integrity_results
            
        except Exception as e:
            error_msg = f"Error during cloud integrity verification: {e}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def repair_cloud_structure(self, integrity_results, progress_callback=None):
        """Repair cloud storage structure based on integrity check results."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return {"success": False, "error": "Cloud sync not available"}
            
            if progress_callback:
                progress_callback(0, "Starting cloud structure repair...")
            
            repair_results = {
                "success": True,
                "metadata_created": 0,
                "metadata_deleted": 0,
                "overall_meta_updated": False,
                "errors": []
            }
            
            # Create missing metadata indexes
            missing_metadata = integrity_results.get("missing_metadata_indexes", [])
            if missing_metadata:
                if progress_callback:
                    progress_callback(10, f"Creating {len(missing_metadata)} missing metadata indexes...")
                
                for i, filename in enumerate(missing_metadata):
                    try:
                        progress = 10 + (i / len(missing_metadata)) * 40
                        if progress_callback:
                            progress_callback(progress, f"Creating metadata for {filename}...")
                        
                        # Load session to extract metadata
                        session_data = self.load_session_from_cloud(filename)
                        if session_data and 'metadata' in session_data:
                            metadata = session_data['metadata']
                        else:
                            # Create basic metadata
                            metadata = {
                                'name': filename.replace('.fastshot', ''),
                                'desc': 'Auto-generated metadata',
                                'tags': [],
                                'color': 'blue',
                                'class': '',
                                'image_count': 0,
                                'file_size': 0,
                                'created_at': datetime.now().isoformat(),
                                'thumbnail_collage': None
                            }
                        
                        if self.save_meta_index_to_cloud(filename, metadata):
                            repair_results["metadata_created"] += 1
                        else:
                            repair_results["errors"].append(f"Failed to create metadata for {filename}")
                    
                    except Exception as e:
                        repair_results["errors"].append(f"Error creating metadata for {filename}: {e}")
            
            # Delete orphaned metadata indexes
            orphaned_metadata = integrity_results.get("orphaned_metadata", [])
            if orphaned_metadata:
                if progress_callback:
                    progress_callback(50, f"Deleting {len(orphaned_metadata)} orphaned metadata indexes...")
                
                for i, filename in enumerate(orphaned_metadata):
                    try:
                        progress = 50 + (i / len(orphaned_metadata)) * 30
                        if progress_callback:
                            progress_callback(progress, f"Deleting orphaned metadata for {filename}...")
                        
                        base_name = filename.replace('.fastshot', '')
                        meta_filename = f"{base_name}.meta.json"
                        s3_key = f"meta_indexes/{meta_filename}"
                        
                        self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                        repair_results["metadata_deleted"] += 1
                    
                    except Exception as e:
                        repair_results["errors"].append(f"Error deleting orphaned metadata for {filename}: {e}")
            
            # Update overall metadata file
            if progress_callback:
                progress_callback(80, "Updating overall metadata file...")
            
            if self.update_overall_meta_file():
                repair_results["overall_meta_updated"] = True
            else:
                repair_results["errors"].append("Failed to update overall metadata file")
            
            if progress_callback:
                progress_callback(100, "Cloud structure repair completed")
            
            print(f"Cloud repair completed: {repair_results['metadata_created']} created, "
                  f"{repair_results['metadata_deleted']} deleted")
            
            return repair_results
            
        except Exception as e:
            error_msg = f"Error during cloud structure repair: {e}"
            print(error_msg)
            return {"success": False, "error": error_msg}
    
    def list_meta_indexes_in_cloud(self):
        """List all metadata index files in cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return []
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='meta_indexes/'
            )
            
            meta_indexes = []
            for obj in response.get('Contents', []):
                filename = obj['Key'].replace('meta_indexes/', '')
                if filename.endswith('.meta.json'):
                    meta_indexes.append({
                        'filename': filename,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })
            
            return meta_indexes
            
        except Exception as e:
            print(f"Error listing metadata indexes in cloud: {e}")
            return []
    
    def _calculate_checksum(self, data):
        """Calculate SHA256 checksum for data."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    def _calculate_file_checksum_from_cloud(self, filename):
        """Calculate checksum for a file in cloud storage."""
        try:
            s3_key = f"sessions/{filename}"
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            
            # Use ETag as checksum if available (for files uploaded in single part)
            etag = response.get('ETag', '').strip('"')
            if etag and '-' not in etag:  # Single part upload
                return f"etag:{etag}"
            
            # For multipart uploads or if ETag is not suitable, download and calculate
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            data = response['Body'].read()
            return f"sha256:{self._calculate_checksum(data)}"
            
        except Exception as e:
            print(f"Error calculating checksum for {filename}: {e}")
            return ""

    # ===== NOTES SYNCHRONIZATION METHODS =====
    
    def save_note_to_cloud(self, note_data):
        """Save a note to cloud storage in quicknotes/notes/ folder."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            note_id = note_data.get('id')
            if not note_id:
                print("Error: Note ID is required")
                return False
            
            # Convert note data to JSON
            json_data = json.dumps(note_data, indent=2, ensure_ascii=False).encode('utf-8')
            
            # Upload to S3 in quicknotes/notes/ folder
            s3_key = f"quicknotes/notes/{note_id}.json"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            print(f"Note saved to cloud: {s3_key}")
            return True
            
        except Exception as e:
            print(f"Error saving note to cloud: {e}")
            return False
    
    def load_note_from_cloud(self, note_id):
        """Load a note from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            s3_key = f"quicknotes/notes/{note_id}.json"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = response['Body'].read()
            
            # Parse JSON
            note_data = json.loads(json_data.decode('utf-8'))
            
            print(f"Note loaded from cloud: {note_id}")
            return note_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print(f"Note not found in cloud: {note_id}")
                return None
            else:
                print(f"Error loading note from cloud: {e}")
                return None
        except Exception as e:
            print(f"Error loading note from cloud: {e}")
            return None
    
    def delete_note_from_cloud(self, note_id):
        """Delete a note from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            # Delete note file
            s3_key = f"quicknotes/notes/{note_id}.json"
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            
            print(f"Note deleted from cloud: {note_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting note from cloud: {e}")
            return False
    
    def get_note_public_url(self, note_id, expiration=3600):
        """Generate a public URL for a note with expiration time."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            s3_key = f"quicknotes/notes/{note_id}.json"
            
            # Generate presigned URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            
            print(f"Generated public URL for note: {note_id}")
            return url
            
        except Exception as e:
            print(f"Error generating public URL for note: {e}")
            return None
    
    def update_notes_overall_index(self):
        """Update the overall notes index file with current notes list."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return False
            
            # List all notes in cloud
            notes_list = self.list_notes_in_cloud()
            
            # Create overall notes index structure
            overall_notes_index = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_notes": len(notes_list),
                "notes": []
            }
            
            # Add note information
            total_words = 0
            total_size = 0
            most_recent_update = None
            
            for note_info in notes_list:
                try:
                    # Load note to get metadata
                    note_data = self.load_note_from_cloud(note_info['id'])
                    if note_data:
                        note_summary = {
                            "id": note_data.get('id'),
                            "title": note_data.get('title', ''),
                            "short_code": note_data.get('short_code', ''),
                            "created_at": note_data.get('created_at'),
                            "updated_at": note_data.get('updated_at'),
                            "file_size": note_info.get('size', 0),
                            "word_count": note_data.get('metadata', {}).get('word_count', 0)
                        }
                        overall_notes_index['notes'].append(note_summary)
                        
                        # Update statistics
                        total_words += note_summary['word_count']
                        total_size += note_summary['file_size']
                        
                        # Track most recent update
                        if note_summary['updated_at']:
                            if not most_recent_update or note_summary['updated_at'] > most_recent_update:
                                most_recent_update = note_summary['updated_at']
                
                except Exception as e:
                    print(f"Warning: Could not process note {note_info.get('id', 'unknown')}: {e}")
                    continue
            
            # Add statistics
            overall_notes_index['statistics'] = {
                "total_words": total_words,
                "total_size_bytes": total_size,
                "most_recent_update": most_recent_update
            }
            
            # Convert to JSON
            json_data = json.dumps(overall_notes_index, indent=2, ensure_ascii=False).encode('utf-8')
            
            # Upload to S3
            s3_key = "quicknotes/overall_notes_index.json"
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json'
            )
            
            print(f"Overall notes index updated with {len(notes_list)} notes")
            return True
            
        except Exception as e:
            print(f"Error updating overall notes index: {e}")
            return False
    
    def load_notes_overall_index(self):
        """Load the overall notes index file from cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return None
            
            s3_key = "quicknotes/overall_notes_index.json"
            
            # Download from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            json_data = response['Body'].read()
            
            # Parse JSON
            overall_notes_index = json.loads(json_data.decode('utf-8'))
            
            print(f"Loaded overall notes index with {overall_notes_index.get('total_notes', 0)} notes")
            return overall_notes_index
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                print("Overall notes index file not found in cloud")
                return None
            else:
                print(f"Error loading overall notes index from cloud: {e}")
                return None
        except Exception as e:
            print(f"Error loading overall notes index from cloud: {e}")
            return None
    
    def list_notes_in_cloud(self):
        """List all notes in cloud storage."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return []
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='quicknotes/notes/'
            )
            
            notes = []
            for obj in response.get('Contents', []):
                filename = obj['Key'].replace('quicknotes/notes/', '')
                if filename.endswith('.json'):
                    note_id = filename.replace('.json', '')
                    notes.append({
                        'id': note_id,
                        'filename': filename,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })
            
            return notes
            
        except Exception as e:
            print(f"Error listing notes in cloud: {e}")
            return []
    
    def rebuild_notes_index(self):
        """Rebuild notes index by downloading all notes from cloud and reconstructing the index."""
        try:
            if not self.cloud_sync_enabled or not self._init_s3_client():
                return {"success": False, "error": "Cloud sync not available"}
            
            # Get list of all notes in cloud
            notes_list = self.list_notes_in_cloud()
            
            if not notes_list:
                # Create empty index if no notes exist
                empty_index = {
                    "version": "1.0",
                    "last_updated": datetime.now().isoformat(),
                    "total_notes": 0,
                    "notes": [],
                    "statistics": {
                        "total_words": 0,
                        "total_size_bytes": 0,
                        "most_recent_update": None
                    }
                }
                
                # Save empty index
                json_data = json.dumps(empty_index, indent=2, ensure_ascii=False).encode('utf-8')
                s3_key = "quicknotes/overall_notes_index.json"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=json_data,
                    ContentType='application/json'
                )
                
                return {"success": True, "message": "Created empty notes index", "total_notes": 0}
            
            # Update the overall index (this will process all notes)
            if self.update_notes_overall_index():
                return {
                    "success": True, 
                    "message": f"Successfully rebuilt notes index with {len(notes_list)} notes",
                    "total_notes": len(notes_list)
                }
            else:
                return {"success": False, "error": "Failed to update notes index"}
            
        except Exception as e:
            error_msg = f"Error rebuilding notes index: {e}"
            print(error_msg)
            return {"success": False, "error": error_msg}

    def test_connection(self):
        """Test cloud connection with detailed error reporting."""
        try:
            if not self._init_s3_client():
                return False, "Failed to initialize S3 client"
            
            print(f"DEBUG: Testing connection to bucket: {self.bucket_name} in region: {self.aws_region}")
            
            # First try to check if we can access AWS at all
            try:
                # Use same SSL and proxy settings for STS client
                ssl_verify = self.config.getboolean('CloudSync', 'ssl_verify', fallback=True)
                sts_config_kwargs = {'region_name': self.aws_region}
                
                if self.proxy_enabled and self.proxy_url:
                    proxies = {
                        'http': self.proxy_url,
                        'https': self.proxy_url
                    }
                    sts_config_kwargs['proxies'] = proxies
                
                sts_client = boto3.client(
                    'sts',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    config=Config(**sts_config_kwargs)
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