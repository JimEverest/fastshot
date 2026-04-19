# plugin_quick_c_hyder.py
"""
Quick Cloud Hyder Plugin

This plugin quickly encrypts files from clipboard and uploads them to cloud storage.
Triggered by pressing Ctrl+Alt alternately 8 times.
"""

import tkinter as tk
from tkinter import messagebox
import os
import tempfile
import time
from pathlib import Path
import win32clipboard
import threading

# Import comprehensive error handling system
try:
    from .utils.error_handler import QuickCloudHyderErrorHandler, ErrorSeverity
    from .utils.clipboard_validator import ClipboardValidator
    from .utils.cloud_error_handler import CloudErrorHandler, CloudOperationError
    # Import proxy header fix to resolve enterprise proxy HTTP parsing issues
    from .utils.proxy_header_fix import apply_proxy_header_fix
except ImportError:
    try:
        # Fallback to absolute imports
        from fastshot.plugins.utils.error_handler import QuickCloudHyderErrorHandler, ErrorSeverity
        from fastshot.plugins.utils.clipboard_validator import ClipboardValidator
        from fastshot.plugins.utils.cloud_error_handler import CloudErrorHandler, CloudOperationError
        from fastshot.plugins.utils.proxy_header_fix import apply_proxy_header_fix
    except ImportError:
        # Fallback to basic error handling if modules not available
        QuickCloudHyderErrorHandler = None
        ClipboardValidator = None
        CloudErrorHandler = None
        CloudOperationError = Exception
        apply_proxy_header_fix = None

def get_clipboard_text():
    """Get text from clipboard."""
    try:
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return data
    except Exception as e:
        print(f"Error reading clipboard: {e}")
        try:
            win32clipboard.CloseClipboard()
        except:
            pass
        return None

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

def show_upload_progress_dialog(title, message):
    """Show an upload progress dialog with progress bar."""
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
    status_text = tk.Label(progress_window, text="准备up...", font=("Arial", 8), fg="gray")
    status_text.pack(pady=5)
    
    progress_window.update()
    
    # Store references for updating
    progress_window.progress_bar = progress_bar
    progress_window.progress_text = progress_text
    progress_window.status_text = status_text
    
    return progress_window

def update_upload_progress(dialog, progress_percent, status_message=""):
    """Update upload progress dialog."""
    if dialog and hasattr(dialog, 'progress_bar'):
        try:
            dialog.progress_bar['value'] = progress_percent
            dialog.progress_text.config(text=f"{progress_percent:.1f}%")
            if status_message:
                dialog.status_text.config(text=status_message)
            dialog.update()
        except:
            pass

def upload_with_progress(cloud_sync, data, s3_key, progress_dialog):
    """Upload data to S3 with progress tracking for large files."""
    try:
        # Initialize S3 client if needed
        if not cloud_sync._init_s3_client():
            return False
        
        # For large files, we'll simulate progress since S3 put_object doesn't provide built-in progress
        # In a real implementation, you might use multipart upload for very large files
        
        total_size = len(data)
        chunk_size = max(1024 * 1024, total_size // 20)  # At least 1MB chunks, max 20 updates
        
        update_upload_progress(progress_dialog, 0, "开始up...")
        
        # Simulate chunked upload progress (S3 put_object is atomic, but we show progress for UX)
        import io
        data_stream = io.BytesIO(data)
        
        # Update progress in steps
        for i in range(10):
            progress = (i + 1) * 10
            update_upload_progress(progress_dialog, progress, f"up中... ({progress}%)")
            time.sleep(0.1)  # Small delay to show progress
        
        # Perform the actual upload
        update_upload_progress(progress_dialog, 90, "完成up...")
        
        cloud_sync.s3_client.put_object(
            Bucket=cloud_sync.bucket_name,
            Key=s3_key,
            Body=data,
            ContentType='image/png'
        )
        
        update_upload_progress(progress_dialog, 100, "up完成")
        time.sleep(0.5)  # Brief pause to show completion
        
        return True
        
    except Exception as e:
        update_upload_progress(progress_dialog, -1, f"up失败: {str(e)}")
        print(f"Upload error: {e}")
        return False

def validate_file_path(file_path):
    """Validate if the file path exists and is accessible."""
    try:
        path = Path(file_path)
        if not path.exists():
            return False, f"Path does not exist: {file_path}"
        
        # Check file/folder size (100MB limit as per design)
        MAX_SIZE = 100 * 1024 * 1024  # 100MB
        
        if path.is_file():
            file_size = path.stat().st_size
            if file_size > MAX_SIZE:
                return False, f"File too large: {file_size / (1024*1024):.1f}MB (max 100MB)"
        elif path.is_dir():
            # Calculate directory size
            total_size = 0
            try:
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                        if total_size > MAX_SIZE:
                            return False, f"Folder too large: >{total_size / (1024*1024):.1f}MB (max 100MB)"
            except (PermissionError, OSError) as e:
                return False, f"Cannot access folder contents: {e}"
        
        return True, str(path.resolve())
    except Exception as e:
        return False, f"Invalid path: {e}"

def run(app_context):
    """Main function called when plugin is activated."""
    print("Quick Cloud Hyder activated!")
    
    # Apply proxy header fix for enterprise environments
    if apply_proxy_header_fix:
        try:
            apply_proxy_header_fix()
        except Exception as e:
            print(f"Warning: Could not apply proxy header fix: {e}")
    
    # Initialize error handling system
    error_handler = None
    clipboard_validator = None
    cloud_error_handler = None
    
    if QuickCloudHyderErrorHandler:
        error_handler = QuickCloudHyderErrorHandler("Quick Cloud Hyder")
        clipboard_validator = ClipboardValidator("Quick Cloud Hyder")
        cloud_error_handler = CloudErrorHandler("Quick Cloud Hyder")
        
        error_handler.log_operation("plugin_activation", {"plugin": "quick_c_hyder"})
    
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
                messagebox.showerror("Error", "sss同步功能不可用，请检查sss同步配置")
                return
            
            if not app_context.cloud_sync.cloud_sync_enabled:
                messagebox.showerror("Error", "sss同步功能未启用，请在设置中启用sss同步")
                return
        
        # Step 2: Read and validate clipboard content
        progress_dialog = show_progress_dialog("Quick Cloud Hyder", "正在读取剪贴板...")
        
        # Import FileHyder early to use its clipboard functionality
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
        
        hyder = FileHyder()
        
        # Use comprehensive clipboard validation
        if clipboard_validator:
            is_valid, error_msg, file_path = clipboard_validator.validate_clipboard_content(hyder)
            if not is_valid:
                close_progress_dialog(progress_dialog)
                clipboard_validator.show_clipboard_error(error_msg)
                return
        else:
            # Fallback clipboard handling
            try:
                clipboard_data = hyder.get_clipboard_file_path()
            except Exception:
                clipboard_data = get_clipboard_text()
            
            if not clipboard_data:
                close_progress_dialog(progress_dialog)
                messagebox.showerror("Error", "剪贴板为空，请先复制文件或文件夹路径到剪贴板")
                return
            
            # Handle different clipboard data types
            if isinstance(clipboard_data, list):
                if len(clipboard_data) == 1:
                    file_path = clipboard_data[0]
                else:
                    close_progress_dialog(progress_dialog)
                    messagebox.showerror("Error", f"剪贴板中包含多个文件（{len(clipboard_data)}个），请选择单个文件或文件夹")
                    return
            elif isinstance(clipboard_data, str):
                file_path = clipboard_data.strip()
            else:
                close_progress_dialog(progress_dialog)
                messagebox.showerror("Error", "剪贴板中的数据格式不支持")
                return
            
            # Validate file path
            is_valid, result = validate_file_path(file_path.strip())
            if not is_valid:
                close_progress_dialog(progress_dialog)
                messagebox.showerror("Error", f"无效的文件路径：\n{result}")
                return
            
            file_path = result
        
        if error_handler:
            error_handler.log_operation("clipboard_validation", 
                                      {"file_path": file_path, "success": True})
        
        print(f"Processing file/folder: {file_path}")
        
        # Step 3: Use FileHyder for encryption
        close_progress_dialog(progress_dialog)
        progress_dialog = show_progress_dialog("Quick Cloud Hyder", "正在encode文件...")
        
        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix="quick_c_hyder_")
        temp_files.append(temp_dir)
        
        # Encrypt and disguise file
        try:
            # Use the cover image from resources
            cover_image_path = os.path.join(os.path.dirname(__file__), '../resources', "tk_color_chart.png")
            
            # Verify cover image exists
            if not os.path.exists(cover_image_path):
                raise Exception(f"Cover image not found: {cover_image_path}")
            
            if error_handler:
                error_handler.log_operation("encoden_start", 
                                          {"file_path": file_path, "temp_dir": temp_dir})
            
            # Get encryption key from config
            encryption_key = "qwer1234"  # Default fallback
            try:
                if hasattr(app_context, 'config') and app_context.config:
                    encryption_key = app_context.config.get('CloudSync', 'encryption_key', fallback="qwer1234")
                elif hasattr(app_context, 'cloud_sync') and hasattr(app_context.cloud_sync, 'encryption_key'):
                    encryption_key = app_context.cloud_sync.encryption_key
                
                if error_handler:
                    error_handler.log_operation("encryption_key_retrieved", 
                                              {"key_source": "config", "key_length": len(encryption_key)})
            except Exception as e:
                if error_handler:
                    error_handler.log_operation("encryption_key_fallback", 
                                              {"error": str(e), "using_default": True})
                print(f"Warning: Could not read encryption key from config, using default: {e}")
            
            # Perform encoding with FileHyder
            encoded_path = hyder.encode(
                file_path=file_path,
                img_path=cover_image_path,
                key=encryption_key,
                output_dir=temp_dir
            )
            
            if not encoded_path or not os.path.exists(encoded_path):
                raise Exception("文件encode失败，未生成输出文件")
            
            # Add the encoded file to temp_files for cleanup
            temp_files.append(encoded_path)
            
            if error_handler:
                error_handler.log_operation("encode_success", 
                                          {"encoded_path": encoded_path})
                
        except Exception as e:
            close_progress_dialog(progress_dialog)
            if error_handler:
                error_handler.handle_error(e, "file encode")
            else:
                error_msg = f"文件encode失败：\n{str(e)}"
                if "Permission denied" in str(e):
                    error_msg += "\n\n可能原因：文件正在被其他程序使用"
                elif "No space left" in str(e):
                    error_msg += "\n\n可能原因：磁盘空间不足"
                messagebox.showerror("Error", error_msg)
            return
        
        print(f"File encode successfully: {encoded_path}")
        
        # Step 4: Upload to cloud
        close_progress_dialog(progress_dialog)
        
        try:
            # Generate unique filename with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            cloud_filename = f"{timestamp}_hyd.png"
            s3_key = f".qc/{cloud_filename}"
            
            # Read the encode file
            with open(encoded_path, 'rb') as f:
                encrypted_data = f.read()
            
            file_size_mb = len(encrypted_data) / (1024 * 1024)
            
            if error_handler:
                error_handler.log_operation("upload_start", 
                                          {"s3_key": s3_key, "file_size_mb": file_size_mb})
            
            # Use comprehensive cloud error handling for upload
            if cloud_error_handler:
                def upload_operation():
                    # Initialize S3 client if needed
                    if not app_context.cloud_sync._init_s3_client():
                        raise Exception("无法初始化S3客户端")
                    
                    # Ensure .qc directory exists by creating it if needed
                    try:
                        app_context.cloud_sync.s3_client.put_object(
                            Bucket=app_context.cloud_sync.bucket_name,
                            Key=".qc/",
                            Body=b'',
                            ContentType='application/x-directory'
                        )
                    except Exception:
                        pass  # Directory creation is optional, upload will work anyway
                    
                    # Upload to S3 using existing cloud sync functionality
                    app_context.cloud_sync.s3_client.put_object(
                        Bucket=app_context.cloud_sync.bucket_name,
                        Key=s3_key,
                        Body=encrypted_data,
                        ContentType='image/png'
                    )
                    return True
                
                # Show appropriate progress dialog based on file size
                if file_size_mb > 5:  # Show detailed progress for files > 5MB
                    progress_dialog = show_upload_progress_dialog("Quick Cloud Hyder", f"正在up文件 ({file_size_mb:.1f} MB)...")
                    
                    def progress_callback(message):
                        update_upload_progress(progress_dialog, -1, message)
                    
                    try:
                        cloud_error_handler.execute_with_retry(
                            upload_operation, 
                            "upload", 
                            progress_callback
                        )
                    except CloudOperationError as e:
                        close_progress_dialog(progress_dialog)
                        cloud_error_handler.show_cloud_error(str(e))
                        return
                    
                    close_progress_dialog(progress_dialog)
                else:
                    # Simple upload for smaller files
                    progress_dialog = show_progress_dialog("Quick Cloud Hyder", "正在upl到sss...")
                    
                    try:
                        cloud_error_handler.execute_with_retry(upload_operation, "upload")
                    except CloudOperationError as e:
                        close_progress_dialog(progress_dialog)
                        cloud_error_handler.show_cloud_error(str(e))
                        return
            else:
                # Fallback upload handling
                # Show appropriate progress dialog based on file size
                if file_size_mb > 5:  # Show detailed progress for files > 5MB
                    progress_dialog = show_upload_progress_dialog("Quick Cloud Hyder", f"正在up文件 ({file_size_mb:.1f} MB)...")
                    
                    # Upload with progress tracking for large files
                    upload_success = upload_with_progress(
                        app_context.cloud_sync,
                        encrypted_data,
                        s3_key,
                        progress_dialog
                    )
                    
                    close_progress_dialog(progress_dialog)
                    
                    if not upload_success:
                        messagebox.showerror("Error", "文件up失败，请检查网络连接")
                        return
                else:
                    # Simple upload for smaller files
                    progress_dialog = show_progress_dialog("Quick Cloud Hyder", "正在up到sss...")
                    
                    # Initialize S3 client if needed
                    if not app_context.cloud_sync._init_s3_client():
                        close_progress_dialog(progress_dialog)
                        messagebox.showerror("Error", "无法初始化S3客户端，请检查云同步配置")
                        return
                    
                    # Ensure .qc directory exists by creating it if needed
                    try:
                        app_context.cloud_sync.s3_client.put_object(
                            Bucket=app_context.cloud_sync.bucket_name,
                            Key=".qc/",
                            Body=b'',
                            ContentType='application/x-directory'
                        )
                    except Exception:
                        pass  # Directory creation is optional, upload will work anyway
                    
                    # Upload to S3 using existing cloud sync functionality
                    app_context.cloud_sync.s3_client.put_object(
                        Bucket=app_context.cloud_sync.bucket_name,
                        Key=s3_key,
                        Body=encrypted_data,
                        ContentType='image/png'
                    )
            
            if error_handler:
                error_handler.log_operation("upload_success", {"s3_key": s3_key})
            
            print(f"File uploaded successfully to: {s3_key}")
            
        except Exception as e:
            close_progress_dialog(progress_dialog)
            if cloud_error_handler:
                cloud_error_handler.handle_cloud_error(e, "upload")
            else:
                error_msg = f"文件up失败：\n{str(e)}"
                if "NoCredentialsError" in str(e):
                    error_msg += "\n\n可能原因：AWS凭证未配置"
                elif "EndpointConnectionError" in str(e):
                    error_msg += "\n\n可能原因：网络连接问题"
                elif "AccessDenied" in str(e):
                    error_msg += "\n\n可能原因：S3权限不足"
                messagebox.showerror("Error", error_msg)
            return
        
        # Step 5: Update last_qc_hyd.txt using atomic tracking system
        close_progress_dialog(progress_dialog)
        progress_dialog = show_progress_dialog("Quick Cloud Hyder", "正在更新记录...")
        
        try:
            # Import the last upload tracker
            try:
                from .utils.last_upload_tracker import LastUploadTracker
            except ImportError:
                try:
                    # Fallback to absolute import
                    from fastshot.plugins.utils.last_upload_tracker import LastUploadTracker
                except ImportError:
                    raise Exception("LastUploadTracker模块不可用")
            
            # Create tracker instance
            tracker = LastUploadTracker(app_context.cloud_sync)
            
            # Create upload record with all required fields
            upload_record = tracker.create_upload_record(
                filename=cloud_filename,
                s3_path=s3_key,
                original_path=file_path,
                file_size=len(encrypted_data),
                file_data=encrypted_data
            )
            
            # Perform atomic update
            update_success = tracker.update_tracking_file_atomic(upload_record)
            
            if not update_success:
                raise Exception("原子更新失败")
            
            print("Last upload record updated successfully with atomic operation")
            
        except Exception as e:
            close_progress_dialog(progress_dialog)
            error_msg = f"文件up成功，但记录更新失败：\n{str(e)}"
            
            # Provide specific error guidance
            if "LastUploadTracker模块不可用" in str(e):
                error_msg += "\n\n可能原因：跟踪模块未正确安装"
            elif "原子更新失败" in str(e):
                error_msg += "\n\n可能原因：sss写入权限不足或网络问题"
            elif "S3 client not available" in str(e):
                error_msg += "\n\n可能原因：sss同步配置无效"
            
            messagebox.showerror("Warning", error_msg)
            # Don't return here, still show success message
        
        # Step 6: Show success message
        close_progress_dialog(progress_dialog)
        
        success_message = f"文件encode up成功！\n\n"
        success_message += f"原始路径: {file_path}\n"
        success_message += f"sss路径: {s3_key}\n"
        success_message += f"文件大小: {len(encrypted_data) / 1024:.1f} KB"
        
        # Use comprehensive success message handling
        if error_handler:
            error_handler.show_success_message(success_message, "操作成功")
            error_handler.log_operation("operation_complete", {
                "file_path": file_path,
                "s3_key": s3_key,
                "file_size_kb": len(encrypted_data) / 1024
            })
        else:
            messagebox.showinfo("Success", success_message)
        
        # Copy cloud path to clipboard for convenience
        copy_to_clipboard(s3_key)
        
    except Exception as e:
        close_progress_dialog(progress_dialog)
        messagebox.showerror("Error", f"操作失败：\n{str(e)}")
        print(f"Quick Cloud Hyder error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup temporary files
        for temp_path in temp_files:
            try:
                if os.path.isdir(temp_path):
                    import shutil
                    shutil.rmtree(temp_path)
                elif os.path.isfile(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                print(f"Warning: Could not clean up temporary file {temp_path}: {e}")

def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'Quick Cloud Hyder',
        'id': 'plugin_quick_c_hyder',
        'description': 'Quick encode and up files using Ctrl+Alt alternate 8 times',
        'author': 'FastShot Team',
        'version': '1.0',
        'default_shortcut': 'ctrl_alt_alternate',
        'press_times': 8,
        'enabled': True
    }