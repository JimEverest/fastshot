# plugin_quick_c_retriver.py
"""
Quick Cloud Retriver Plugin

This plugin quickly downloads and decrypts the last uploaded file from cloud storage.
Triggered by pressing Ctrl+Win alternately 8 times.
"""

import tkinter as tk
from tkinter import messagebox
import os
import tempfile
import json
import time
from pathlib import Path
import win32clipboard
import threading

# Import comprehensive error handling system
try:
    from .utils.error_handler import QuickCloudHyderErrorHandler, ErrorSeverity
    from .utils.cloud_error_handler import CloudErrorHandler, CloudOperationError
    # Import proxy header fix to resolve enterprise proxy HTTP parsing issues
    from .utils.proxy_header_fix import apply_proxy_header_fix
except ImportError:
    try:
        # Fallback to absolute imports
        from fastshot.plugins.utils.error_handler import QuickCloudHyderErrorHandler, ErrorSeverity
        from fastshot.plugins.utils.cloud_error_handler import CloudErrorHandler, CloudOperationError
        from fastshot.plugins.utils.proxy_header_fix import apply_proxy_header_fix
    except ImportError:
        # Fallback to basic error handling if modules not available
        QuickCloudHyderErrorHandler = None
        CloudErrorHandler = None
        CloudOperationError = Exception
        apply_proxy_header_fix = None

def copy_to_clipboard(text):
    """Copy text to clipboard."""
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        print(f"Copied to clipboard: {text}")
    except Exception as e:
        print(f"Error copying to clipboard: {e}")

def show_progress_dialog(title, message):
    """Show a simple progress dialog."""
    progress_window = tk.Toplevel()
    progress_window.title(title)
    progress_window.geometry("400x150")
    progress_window.resizable(False, False)
    
    # Center the window
    progress_window.update_idletasks()
    x = (progress_window.winfo_screenwidth() // 2) - (400 // 2)
    y = (progress_window.winfo_screenheight() // 2) - (150 // 2)
    progress_window.geometry(f"400x150+{x}+{y}")
    
    # Make it stay on top
    progress_window.attributes('-topmost', True)
    
    label = tk.Label(progress_window, text=message, font=("Arial", 10), wraplength=350)
    label.pack(pady=30)
    
    progress_window.update()
    return progress_window

def close_progress_dialog(dialog):
    """Close progress dialog."""
    if dialog:
        try:
            dialog.destroy()
        except:
            pass

def show_download_progress_dialog(title, message):
    """Show a download progress dialog with progress bar."""
    progress_window = tk.Toplevel()
    progress_window.title(title)
    progress_window.geometry("450x200")
    progress_window.resizable(False, False)
    
    # Center the window
    progress_window.update_idletasks()
    x = (progress_window.winfo_screenwidth() // 2) - (450 // 2)
    y = (progress_window.winfo_screenheight() // 2) - (200 // 2)
    progress_window.geometry(f"450x200+{x}+{y}")
    
    # Make it stay on top
    progress_window.attributes('-topmost', True)
    
    # Message label
    label = tk.Label(progress_window, text=message, font=("Arial", 10), wraplength=400)
    label.pack(pady=20)
    
    # Progress bar
    from tkinter import ttk
    progress_bar = ttk.Progressbar(progress_window, length=350, mode='determinate')
    progress_bar.pack(pady=10)
    
    # Progress text
    progress_text = tk.Label(progress_window, text="0%", font=("Arial", 9))
    progress_text.pack(pady=5)
    
    # Status text
    status_text = tk.Label(progress_window, text="准备dl...", font=("Arial", 8), fg="gray")
    status_text.pack(pady=5)
    
    progress_window.update()
    
    # Store references for updating
    progress_window.progress_bar = progress_bar
    progress_window.progress_text = progress_text
    progress_window.status_text = status_text
    
    return progress_window

def update_download_progress(dialog, progress_percent, status_message=""):
    """Update download progress dialog."""
    if dialog and hasattr(dialog, 'progress_bar'):
        try:
            dialog.progress_bar['value'] = progress_percent
            dialog.progress_text.config(text=f"{progress_percent:.1f}%")
            if status_message:
                dialog.status_text.config(text=status_message)
            dialog.update()
        except:
            pass

def download_with_progress(cloud_sync, s3_key, progress_dialog, max_retries=3):
    """Download file from S3 with progress tracking and retry logic for large files."""
    import time
    from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
    
    for attempt in range(max_retries):
        try:
            # Initialize S3 client if needed
            if not cloud_sync._init_s3_client():
                return None
            
            update_download_progress(progress_dialog, 0, f"开始dl.. (尝试 {attempt + 1}/{max_retries})")
            
            # Get object info first to check size
            try:
                head_response = cloud_sync.s3_client.head_object(
                    Bucket=cloud_sync.bucket_name,
                    Key=s3_key
                )
                file_size = head_response.get('ContentLength', 0)
                file_size_mb = file_size / (1024 * 1024) if file_size > 0 else 0
            except Exception as e:
                file_size = 0
                file_size_mb = 0
                print(f"Warning: Could not get file size: {e}")
            
            # For large files, use streaming download with real progress tracking
            if file_size > 10 * 1024 * 1024:  # 10MB threshold for streaming
                update_download_progress(progress_dialog, 5, f"dl大文件 ({file_size_mb:.1f} MB)...")
                
                response = cloud_sync.s3_client.get_object(
                    Bucket=cloud_sync.bucket_name,
                    Key=s3_key
                )
                
                # Stream download with progress tracking
                body = response['Body']
                encrypted_data = b''
                downloaded = 0
                
                chunk_size = 1024 * 1024  # 1MB chunks
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break
                    
                    encrypted_data += chunk
                    downloaded += len(chunk)
                    
                    if file_size > 0:
                        progress = min(95, 10 + (downloaded / file_size) * 80)
                        status = f"已dl {downloaded / (1024*1024):.1f} MB / {file_size_mb:.1f} MB"
                        update_download_progress(progress_dialog, progress, status)
                
                update_download_progress(progress_dialog, 100, "dl完成")
                time.sleep(0.3)  # Brief pause to show completion
                
                return encrypted_data
            
            else:
                # For smaller files, use simple download with simulated progress
                update_download_progress(progress_dialog, 10, "dl中...")
                
                # Update progress in steps for UX
                for i in range(8):
                    progress = 10 + (i + 1) * 10
                    update_download_progress(progress_dialog, progress, f"dl中... ({progress}%)")
                    time.sleep(0.05)  # Small delay to show progress
                
                # Perform the actual download
                update_download_progress(progress_dialog, 90, "完成dl...")
                
                response = cloud_sync.s3_client.get_object(
                    Bucket=cloud_sync.bucket_name,
                    Key=s3_key
                )
                encrypted_data = response['Body'].read()
                
                update_download_progress(progress_dialog, 100, "dl完成")
                time.sleep(0.3)  # Brief pause to show completion
                
                return encrypted_data
                
        except (EndpointConnectionError, ConnectionError) as e:
            error_msg = f"网络连接错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
            print(f"Network error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                update_download_progress(progress_dialog, -1, f"{error_msg} - 重试中...")
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                continue
            else:
                update_download_progress(progress_dialog, -1, f"网络连接失败，已重试 {max_retries} 次")
                return None
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = f"AWS错误 ({error_code}): {str(e)}"
            print(f"AWS ClientError on attempt {attempt + 1}: {e}")
            
            # Don't retry for certain errors
            if error_code in ['NoSuchKey', 'AccessDenied', 'InvalidBucketName']:
                update_download_progress(progress_dialog, -1, error_msg)
                return None
            
            if attempt < max_retries - 1:
                update_download_progress(progress_dialog, -1, f"{error_msg} - 重试中...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                update_download_progress(progress_dialog, -1, f"下载失败，已重试 {max_retries} 次")
                return None
                
        except Exception as e:
            error_msg = f"下载错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
            print(f"Download error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                update_download_progress(progress_dialog, -1, f"{error_msg} - 重试中...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                update_download_progress(progress_dialog, -1, f"下载失败，已重试 {max_retries} 次")
                return None
    
    return None

def run(app_context):
    """Main function called when plugin is activated."""
    print("Quick Cloud Retriver activated!")
    
    # Apply proxy header fix for enterprise environments
    if apply_proxy_header_fix:
        try:
            apply_proxy_header_fix()
        except Exception as e:
            print(f"Warning: Could not apply proxy header fix: {e}")
    
    # Initialize error handling system
    error_handler = None
    cloud_error_handler = None
    
    if QuickCloudHyderErrorHandler:
        error_handler = QuickCloudHyderErrorHandler("Quick Cloud Retriver")
        cloud_error_handler = CloudErrorHandler("Quick Cloud Retriver")
        
        error_handler.log_operation("plugin_activation", {"plugin": "quick_c_retriver"})
    
    progress_dialog = None
    temp_files = []  # Track temporary files for cleanup
    
    try:
        # Step 1: Validate prerequisites
        if cloud_error_handler:
            is_valid, error_msg = cloud_error_handler.validate_cloud_prerequisites(app_context)
            if not is_valid:
                if error_handler:
                    error_handler.show_error_dialog(error_msg, ErrorSeverity.ERROR, 
                                                  error_handler.categorize_error(Exception(error_msg)))
                else:
                    messagebox.showerror("Error", error_msg)
                return
        else:
            # Fallback validation
            if not hasattr(app_context, 'cloud_sync') or not app_context.cloud_sync:
                messagebox.showerror("Error", "sss同步功能不可用，请检查云同步配置")
                return
            
            if not app_context.cloud_sync.cloud_sync_enabled:
                messagebox.showerror("Error", "sss同步功能未启用，请在设置中启用云同步")
                return
        
        # Step 2: Read last_qc_hyd.txt from cloud with comprehensive error handling
        progress_dialog = show_progress_dialog("Quick Cloud Retriver", "正在读取upl记录...")
        
        last_upload_record = None
        s3_path = None
        original_path = "Unknown"
        upload_time = "Unknown"
        
        # Use comprehensive cloud error handling for reading upload record
        if cloud_error_handler:
            def read_upload_record():
                # Initialize S3 client if needed
                if not app_context.cloud_sync._init_s3_client():
                    raise Exception("无法初始化S3客户端")
                
                # Download the last upload record
                response = app_context.cloud_sync.s3_client.get_object(
                    Bucket=app_context.cloud_sync.bucket_name,
                    Key=".qc/last_qc_hyd.txt"
                )
                record_data = response['Body'].read().decode('utf-8')
                return json.loads(record_data)
            
            try:
                last_upload_record = cloud_error_handler.execute_with_retry(
                    read_upload_record, 
                    "read"
                )
                
                # Validate record format
                last_upload = last_upload_record.get('last_upload')
                if not last_upload:
                    raise Exception("上传记录格式无效")
                
                s3_path = last_upload.get('s3_path')
                original_path = last_upload.get('original_path', 'Unknown')
                upload_time = last_upload.get('upload_time', 'Unknown')
                
                if not s3_path:
                    raise Exception("上传记录中缺少文件路径")
                
                if error_handler:
                    error_handler.log_operation("read_upload_record", 
                                              {"s3_path": s3_path, "success": True})
                
                print(f"Found last upload: {s3_path}")
                
            except CloudOperationError as e:
                close_progress_dialog(progress_dialog)
                cloud_error_handler.show_cloud_error(str(e))
                return
            except Exception as e:
                close_progress_dialog(progress_dialog)
                if error_handler:
                    error_handler.handle_error(e, "upload record validation")
                else:
                    messagebox.showerror("Error", f"上传记录验证失败：{str(e)}")
                return
        else:
            # Fallback handling for reading upload record
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    # Initialize S3 client if needed
                    if not app_context.cloud_sync._init_s3_client():
                        raise Exception("无法初始化S3客户端")
                    
                    # Download the last upload record
                    response = app_context.cloud_sync.s3_client.get_object(
                        Bucket=app_context.cloud_sync.bucket_name,
                        Key=".qc/last_qc_hyd.txt"
                    )
                    record_data = response['Body'].read().decode('utf-8')
                    last_upload_record = json.loads(record_data)
                    
                    # Validate record format
                    last_upload = last_upload_record.get('last_upload')
                    if not last_upload:
                        raise Exception("上传记录格式无效")
                    
                    s3_path = last_upload.get('s3_path')
                    original_path = last_upload.get('original_path', 'Unknown')
                    upload_time = last_upload.get('upload_time', 'Unknown')
                    
                    if not s3_path:
                        raise Exception("上传记录中缺少文件路径")
                    
                    print(f"Found last upload: {s3_path}")
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
                    
                    print(f"Error reading upload record on attempt {attempt + 1}: {e}")
                    
                    # Handle specific errors that shouldn't be retried
                    if ("NoSuchKey" in str(e) or 
                        "NoCredentialsError" in str(e) or 
                        "AccessDenied" in str(e) or
                        "InvalidBucketName" in str(e)):
                        # Don't retry for these errors
                        break
                    
                    # For network errors, retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        print(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Final attempt failed
                        break
            
            # Check if we successfully got the record
            if not last_upload_record or not s3_path:
                close_progress_dialog(progress_dialog)
                error_msg = f"读取上传记录失败"
                
                # Provide specific error guidance based on the last exception
                try:
                    # Try one more time to get a specific error message
                    response = app_context.cloud_sync.s3_client.get_object(
                        Bucket=app_context.cloud_sync.bucket_name,
                        Key=".qc/last_qc_hyd.txt"
                    )
                except Exception as e:
                    if "NoSuchKey" in str(e):
                        error_msg = "未找到上传记录，请先使用Quick Cloud Hyder上传文件"
                    elif "NoCredentialsError" in str(e):
                        error_msg = "AWS凭证未配置，请检查云同步设置"
                    elif "EndpointConnectionError" in str(e):
                        error_msg = "网络连接问题，请检查网络连接"
                    elif "AccessDenied" in str(e):
                        error_msg = "S3权限不足，请检查AWS权限设置"
                    elif "timeout" in str(e).lower():
                        error_msg = f"网络超时，已重试 {max_retries} 次，请稍后重试"
                    else:
                        error_msg = f"读取上传记录失败：{str(e)}"
                
                messagebox.showerror("Error", error_msg)
                return
        
        # Step 3: Download PNG file from cloud with comprehensive error handling
        close_progress_dialog(progress_dialog)
        
        try:
            # Create temporary directory for processing
            temp_dir = tempfile.mkdtemp(prefix="quick_c_retriver_")
            temp_files.append(temp_dir)
            
            # Check file size first to determine progress dialog type
            file_size_mb = 0
            try:
                head_response = app_context.cloud_sync.s3_client.head_object(
                    Bucket=app_context.cloud_sync.bucket_name,
                    Key=s3_path
                )
                file_size = head_response.get('ContentLength', 0)
                file_size_mb = file_size / (1024 * 1024)
            except Exception as e:
                if error_handler:
                    error_handler.log_operation("file_size_check", 
                                              {"s3_path": s3_path, "error": str(e)})
            
            # Use comprehensive cloud error handling for download
            if cloud_error_handler:
                def download_operation():
                    # Initialize S3 client if needed
                    if not app_context.cloud_sync._init_s3_client():
                        raise Exception("无法初始化S3客户端")
                    
                    # Download the encrypted PNG file
                    response = app_context.cloud_sync.s3_client.get_object(
                        Bucket=app_context.cloud_sync.bucket_name,
                        Key=s3_path
                    )
                    return response['Body'].read()
                
                # Show appropriate progress dialog based on file size
                if file_size_mb > 5:  # Show detailed progress for files > 5MB
                    progress_dialog = show_download_progress_dialog("Quick Cloud Retriver", f"正在下载文件 ({file_size_mb:.1f} MB)...")
                    
                    def progress_callback(message):
                        update_download_progress(progress_dialog, -1, message)
                    
                    try:
                        encrypted_data = cloud_error_handler.execute_with_retry(
                            download_operation, 
                            "download", 
                            progress_callback
                        )
                    except CloudOperationError as e:
                        close_progress_dialog(progress_dialog)
                        cloud_error_handler.show_cloud_error(str(e))
                        return
                    
                    close_progress_dialog(progress_dialog)
                else:
                    # Simple download for smaller files
                    progress_dialog = show_progress_dialog("Quick Cloud Retriver", "正在下载文件...")
                    
                    try:
                        encrypted_data = cloud_error_handler.execute_with_retry(
                            download_operation, 
                            "download"
                        )
                    except CloudOperationError as e:
                        close_progress_dialog(progress_dialog)
                        cloud_error_handler.show_cloud_error(str(e))
                        return
            else:
                # Fallback download handling
                # Show appropriate progress dialog based on file size
                if file_size_mb > 5:  # Show detailed progress for files > 5MB
                    progress_dialog = show_download_progress_dialog("Quick Cloud Retriver", f"正在下载文件 ({file_size_mb:.1f} MB)...")
                    
                    # Download with progress tracking for large files
                    encrypted_data = download_with_progress(
                        app_context.cloud_sync,
                        s3_path,
                        progress_dialog
                    )
                    
                    close_progress_dialog(progress_dialog)
                    
                    if not encrypted_data:
                        messagebox.showerror("Error", "文件下载失败，请检查网络连接")
                        return
                else:
                    # Simple download for smaller files with retry logic
                    progress_dialog = show_progress_dialog("Quick Cloud Retriver", "正在下载文件...")
                    
                    # Download with retry logic for smaller files
                    encrypted_data = None
                    max_retries = 3
                    
                    for attempt in range(max_retries):
                        try:
                            # Initialize S3 client if needed
                            if not app_context.cloud_sync._init_s3_client():
                                raise Exception("无法初始化S3客户端")
                            
                            # Download the encrypted PNG file
                            response = app_context.cloud_sync.s3_client.get_object(
                                Bucket=app_context.cloud_sync.bucket_name,
                                Key=s3_path
                            )
                            encrypted_data = response['Body'].read()
                            break  # Success, exit retry loop
                            
                        except Exception as e:
                            from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
                            
                            print(f"Error downloading file on attempt {attempt + 1}: {e}")
                            
                            # Handle specific errors that shouldn't be retried
                            if ("NoSuchKey" in str(e) or 
                                "AccessDenied" in str(e) or
                                "InvalidBucketName" in str(e)):
                                # Don't retry for these errors
                                break
                            
                            # For network errors, retry with exponential backoff
                            if attempt < max_retries - 1:
                                wait_time = 2 ** attempt  # 1s, 2s, 4s
                                print(f"Retrying download in {wait_time} seconds...")
                                time.sleep(wait_time)
                                continue
                            else:
                                # Final attempt failed
                                break
                    
                    if not encrypted_data:
                        raise Exception("文件dl失败，已重试多次")
            
            # Save to temporary file
            temp_png_path = os.path.join(temp_dir, "encrypted.png")
            with open(temp_png_path, 'wb') as f:
                f.write(encrypted_data)
            
            if error_handler:
                error_handler.log_operation("download_success", 
                                          {"s3_path": s3_path, "temp_path": temp_png_path})
            
            print(f"File downloaded successfully: {temp_png_path}")
            
        except Exception as e:
            close_progress_dialog(progress_dialog)
            if cloud_error_handler:
                cloud_error_handler.handle_cloud_error(e, "download")
            else:
                error_msg = f"文件下载失败：\n{str(e)}"
                
                # Provide specific error guidance
                if "NoSuchKey" in str(e):
                    error_msg = f"sss文件不存在：{s3_path}\n\n可能原因：文件已被删除或路径错误"
                elif "NoCredentialsError" in str(e):
                    error_msg += "\n\n可能原因：AWS凭证未配置"
                elif "EndpointConnectionError" in str(e):
                    error_msg += "\n\n可能原因：网络连接问题"
                elif "AccessDenied" in str(e):
                    error_msg += "\n\n可能原因：S3权限不足"
                elif "timeout" in str(e).lower():
                    error_msg += "\n\n可能原因：网络超时，请重试"
                
                messagebox.showerror("Error", error_msg)
            return
        
        # Step 4: Use FileHyder to decrypt and extract
        close_progress_dialog(progress_dialog)
        progress_dialog = show_progress_dialog("Quick Cloud Retriver", "正在decode文件...")
        
        try:
            from .utils.hyder import FileHyder
        except ImportError:
            try:
                # Fallback to absolute import
                from fastshot.plugins.utils.hyder import FileHyder
            except ImportError:
                close_progress_dialog(progress_dialog)
                error_msg = "FileHyder工具不可用，请检查utils.hyder模块"
                if error_handler:
                    error_handler.handle_error(ImportError(error_msg), "FileHyder import")
                else:
                    messagebox.showerror("Error", error_msg)
                return
        
        try:
            # Initialize FileHyder
            hyder = FileHyder()
            
            # Create output directory for decrypted files
            output_dir = os.path.join(temp_dir, "decrypted")
            os.makedirs(output_dir, exist_ok=True)
            
            if error_handler:
                error_handler.log_operation("decryption_start", 
                                          {"temp_png_path": temp_png_path, "output_dir": output_dir})
            
            # Get encryption key from config
            encryption_key = "qwer1234"  # Default fallback
            try:
                if hasattr(app_context, 'config') and app_context.config:
                    encryption_key = app_context.config.get('CloudSync', 'encryption_key', fallback="qwer1234")
                elif hasattr(app_context, 'cloud_sync') and hasattr(app_context.cloud_sync, 'encryption_key'):
                    encryption_key = app_context.cloud_sync.encryption_key
                
                if error_handler:
                    error_handler.log_operation("decryption_key_retrieved", 
                                              {"key_source": "config", "key_length": len(encryption_key)})
            except Exception as e:
                if error_handler:
                    error_handler.log_operation("decryption_key_fallback", 
                                              {"error": str(e), "using_default": True})
                print(f"Warning: Could not read encryption key from config, using default: {e}")
            
            # Decrypt and extract file
            decoded_folder = hyder.decode(
                img_path=temp_png_path,
                key=encryption_key,
                output_dir=output_dir
            )
            
            if not decoded_folder or not os.path.exists(decoded_folder):
                raise Exception("文件decode失败，未生成输出文件")
            
            if error_handler:
                error_handler.log_operation("decryption_success", 
                                          {"decoded_folder": decoded_folder})
            
            print(f"File decrypted successfully: {decoded_folder}")
            
        except Exception as e:
            close_progress_dialog(progress_dialog)
            if error_handler:
                error_handler.handle_error(e, "file decryption")
            else:
                error_msg = f"文件decode失败：\n{str(e)}"
                
                # Provide specific error guidance
                if "Invalid key" in str(e) or "key" in str(e).lower():
                    error_msg += "\n\n可能原因：decode密钥不正确"
                
                messagebox.showerror("Error", error_msg)
            return
        
        # Step 5: Copy output path to clipboard and show success
        close_progress_dialog(progress_dialog)
        
        # Copy the decoded folder path to clipboard
        copy_to_clipboard(decoded_folder)
        
        success_message = f"文件decode dl成功！\n\n"
        success_message += f"原始路径: {original_path}\n"
        success_message += f"上传时间: {upload_time}\n"
        success_message += f"decode输出: {decoded_folder}\n\n"
        success_message += "输出路径已复制到剪贴板"
        
        # Use comprehensive success message handling
        if error_handler:
            error_handler.show_success_message(success_message, "操作成功")
            error_handler.log_operation("operation_complete", {
                "original_path": original_path,
                "s3_path": s3_path,
                "decoded_folder": decoded_folder
            })
        else:
            messagebox.showinfo("Success", success_message)
        
        # Optionally open the output folder
        try:
            import subprocess
            subprocess.Popen(f'explorer "{decoded_folder}"')
        except Exception as e:
            if error_handler:
                error_handler.log_operation("folder_open_failed", {"error": str(e)})
            print(f"Could not open output folder: {e}")
        
    except Exception as e:
        close_progress_dialog(progress_dialog)
        messagebox.showerror("Error", f"操作失败：\n{str(e)}")
        print(f"Quick Cloud Retriver error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Note: We don't clean up temp_files here because the user needs access to the decrypted files
        # The temporary files will be cleaned up by the system eventually
        print(f"Temporary files preserved at: {temp_files}")

def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'Quick Cloud Retriver',
        'id': 'plugin_quick_c_retriver',
        'description': 'Quick download and decode files from sss using Ctrl+Win alternate 8 times',
        'author': 'FastShot Team',
        'version': '1.0',
        'default_shortcut': 'ctrl_win_alternate',
        'press_times': 8,
        'enabled': True
    }