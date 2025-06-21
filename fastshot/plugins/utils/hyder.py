import os
import zipfile
import re
import win32clipboard
from win32con import CF_HDROP, CF_UNICODETEXT
from shutil import copyfile
from PIL import Image
import datetime
import sys

class FileHyder:
    MARKER = b'FHDR'  # 用于标识加密数据的起始位置

    def __init__(self):
        pass

    def normalize_path(self, path):
        """
        将路径中的反斜杠和多余的正斜杠规范化为单一的正斜杠。
        例如:
            "C:\\Users\\Admin\\file.txt" -> "C:/Users/Admin/file.txt"
            "C://Users//Admin//file.txt" -> "C:/Users/Admin/file.txt"
        """
        path = path.replace('\\', '/')
        path = re.sub(r'/+', '/', path)
        return path

    def get_clipboard_file_path(self):
        """
        从剪贴板中获取文件路径或字符串。
        如果剪贴板中是文件/文件夹，返回路径字符串列表。
        如果剪贴板中是字符串，返回字符串。
        如果剪贴板为空或不支持的格式，返回 None。
        """
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
                files = win32clipboard.GetClipboardData(CF_HDROP)
                normalized_files = [self.normalize_path(file) for file in files]
                return normalized_files
            elif win32clipboard.IsClipboardFormatAvailable(CF_UNICODETEXT):
                text = win32clipboard.GetClipboardData(CF_UNICODETEXT).strip()
                if not text:
                    return None
                normalized_text = self.normalize_path(text)
                # 判断是否为存在的路径
                if os.path.exists(normalized_text):
                    return normalized_text
                else:
                    return text
            else:
                return None
        except Exception as e:
            print(f"从剪贴板获取数据时发生错误: {e}")
            return None
        finally:
            win32clipboard.CloseClipboard()

    def _create_zip(self, file_path):
        """
        将文件或文件夹压缩成 ZIP 文件。
        返回 ZIP 文件路径。
        """
        zip_path = file_path + '.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isdir(file_path):
                for root, dirs, files in os.walk(file_path):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, os.path.join(file_path, os.pardir))
                        zipf.write(abs_path, rel_path)
            else:
                zipf.write(file_path, os.path.basename(file_path))
        return zip_path

    def _encrypt_file(self, input_path, output_path, key):
        """
        使用 XOR 加密算法对文件进行加密。
        """
        key_bytes = key.encode()
        key_len = len(key_bytes)
        with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
            byte = fin.read(1)
            index = 0
            while byte:
                fout.write(bytes([byte[0] ^ key_bytes[index % key_len]]))
                byte = fin.read(1)
                index += 1

    def _decrypt_file(self, input_path, output_path, key):
        """
        使用 XOR 解密算法对文件进行解密。
        """
        self._encrypt_file(input_path, output_path, key)  # XOR 解密与加密相同

    def _create_encrypted_zip(self, file_path, key):
        """
        将文件或文件夹压缩并加密，返回加密后的 ZIP 文件路径。
        """
        zip_path = self._create_zip(file_path)
        encrypted_zip_path = zip_path + '.enc'
        self._encrypt_file(zip_path, encrypted_zip_path, key)
        os.remove(zip_path)  # 删除未加密的 ZIP 文件
        return encrypted_zip_path

    def encode(self, file_path=None, img_path=None, key="qwer1234", output_dir="."):
        """
        将文件或文件夹伪装到图像文件中。
        参数:
            file_path (str): 要伪装的文件或文件夹路径。如果为 None，将从剪贴板获取。
            img_path (str): 伪装用的图像文件路径。如果为 None，将从剪贴板获取。
            key (str): 加密密钥，默认为 "qwer1234"。
            output_dir (str): 输出目录，默认为当前目录。
        返回:
            str: 生成的伪装图像文件的绝对路径。
        """
        # 将 output_dir 转换为绝对路径
        output_dir = os.path.abspath(output_dir)

        # 获取文件路径
        if not file_path:
            clipboard_data = self.get_clipboard_file_path()
            if isinstance(clipboard_data, list):
                if len(clipboard_data) == 1:
                    file_path = clipboard_data[0]
                else:
                    print("剪贴板中包含多个文件，请指定要伪装的单个文件或文件夹路径。")
                    return None
            elif isinstance(clipboard_data, str):
                file_path = clipboard_data
            else:
                print("未提供文件路径，且剪贴板中没有有效的文件路径或字符串。")
                return None

        # 获取图像路径
        if not img_path:
            clipboard_data = self.get_clipboard_file_path()
            if isinstance(clipboard_data, list):
                if len(clipboard_data) == 1 and os.path.isfile(clipboard_data[0]):
                    img_path = clipboard_data[0]
                else:
                    print("剪贴板中包含多个文件或非图像文件，请指定单个图像文件路径。")
                    return None
            elif isinstance(clipboard_data, str):
                img_path = clipboard_data
            else:
                print("未提供图像路径，且剪贴板中没有有效的图像路径或字符串。")
                return None

        # 检查图像文件是否存在
        if not os.path.isfile(img_path):
            print(f"图像文件不存在: {img_path}")
            return None

        # 创建 ZIP 并加密
        encrypted_zip_path = self._create_encrypted_zip(file_path, key)

        # 生成带时间戳的输出文件名
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
        output_img_name = f"{timestamp}.png"
        output_img_path = os.path.join(output_dir, output_img_name)
        output_img_path = os.path.abspath(output_img_path)  # 转换为绝对路径

        # 创建输出目录如果不存在
        os.makedirs(output_dir, exist_ok=True)

        # 复制原始图像到输出路径
        copyfile(img_path, output_img_path)

        # 将标记和加密的 ZIP 文件附加到图像文件
        with open(output_img_path, 'ab') as img, open(encrypted_zip_path, 'rb') as zip_file:
            img.write(self.MARKER)  # 添加标记
            while True:
                chunk = zip_file.read(4096)
                if not chunk:
                    break
                img.write(chunk)

        # 删除加密的 ZIP 文件
        os.remove(encrypted_zip_path)

        print(f"编码后的文件已创建: {output_img_path}")
        return output_img_path

    def decode(self, img_path=None, key="qwer1234", output_dir="."):
        """
        从伪装的图像文件中提取并解压隐藏的文件或文件夹。
        参数:
            img_path (str): 伪装的图像文件路径。如果为 None，将从剪贴板获取。
            key (str): 解密密钥，默认为 "qwer1234"。
            output_dir (str): 输出目录，默认为当前目录。
        返回:
            str: 解压后的文件或文件夹的绝对路径。
        """
        # 将 output_dir 转换为绝对路径
        output_dir = os.path.abspath(output_dir)

        # 获取图像路径
        if not img_path:
            clipboard_data = self.get_clipboard_file_path()
            if isinstance(clipboard_data, list):
                if len(clipboard_data) == 1 and os.path.isfile(clipboard_data[0]):
                    img_path = clipboard_data[0]
                else:
                    print("剪贴板中包含多个文件或非图像文件，请指定单个图像文件路径。")
                    return None
            elif isinstance(clipboard_data, str):
                img_path = clipboard_data
            else:
                print("未提供图像路径，且剪贴板中没有有效的图像路径或字符串。")
                return None

        # 检查图像文件是否存在
        if not os.path.isfile(img_path):
            print(f"图像文件不存在: {img_path}")
            return None

        # 创建输出文件夹
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        folder_name = os.path.join(output_dir, base_name)
        folder_name = os.path.abspath(folder_name)  # 转换为绝对路径
        os.makedirs(folder_name, exist_ok=True)

        # 读取图像文件并提取加密的 ZIP 数据
        with open(img_path, 'rb') as img_file:
            img_data = img_file.read()
            marker_index = img_data.find(self.MARKER)
            if marker_index == -1:
                print("未在图像文件中找到隐藏的加密 ZIP 数据。")
                return None
            encrypted_zip_data = img_data[marker_index + len(self.MARKER):]

        if not encrypted_zip_data:
            print("没有找到加密的 ZIP 数据。")
            return None

        # 将加密的 ZIP 数据写入临时文件
        temp_encrypted_zip_path = os.path.join(folder_name, "hidden.zip.enc")
        temp_encrypted_zip_path = os.path.abspath(temp_encrypted_zip_path)  # 转换为绝对路径
        with open(temp_encrypted_zip_path, 'wb') as temp_zip_file:
            temp_zip_file.write(encrypted_zip_data)

        # 解密 ZIP 文件
        decrypted_zip_path = os.path.join(folder_name, "hidden.zip")
        decrypted_zip_path = os.path.abspath(decrypted_zip_path)  # 转换为绝对路径
        self._decrypt_file(temp_encrypted_zip_path, decrypted_zip_path, key)
        os.remove(temp_encrypted_zip_path)  # 删除加密的临时 ZIP 文件

        # 解压 ZIP 文件
        try:
            with zipfile.ZipFile(decrypted_zip_path, 'r') as zip_ref:
                zip_ref.extractall(folder_name)
            print(f"解码后的文件已提取到: {folder_name}")
            return folder_name
        except zipfile.BadZipFile:
            print("解密后的文件不是有效的 ZIP 文件。可能是密钥错误或文件损坏。")
            return None
        finally:
            # 删除解密的 ZIP 文件
            if os.path.exists(decrypted_zip_path):
                os.remove(decrypted_zip_path)
