"""
Hyder Tool - PNG Steganography Desktop App
Encode/decode files or text into PNG images with XOR encryption.

与 fastshot 插件 (FileHyder) 使用完全相同的Codec算法 (XOR + FHDR marker)，
因此本工具生成的Transformer PNG 可以被 fastshot 插件解码，反之亦然。

Usage: python hyder_tool.py

"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import struct
import zipfile
import datetime
import tempfile
import shutil


# ── Core encode / decode logic (no external deps beyond stdlib) ──────────────

MARKER = b'FHDR'
# Payload format after MARKER:
#   4 bytes  — payload length (big-endian uint32, XOR'd with key)
#   N bytes  — XOR-encrypted zip payload
#   M bytes  — (optional) XOR-encrypted random padding

_LEN_STRUCT = struct.Struct('>I')  # 4-byte big-endian unsigned int


def xor_bytes(data: bytes, key: str) -> bytes:
    """XOR encrypt/decrypt — symmetric operation."""
    key_bytes = key.encode()
    key_len = len(key_bytes)
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ key_bytes[i % key_len]
    return bytes(out)


def encode_to_png(source_path: str, cover_png: str, key: str, output_dir: str,
                  target_size: int = 0) -> str:
    """Zip + XOR-encrypt source file/folder, append after cover PNG with MARKER.

    When target_size > natural size, a 4-byte length header is inserted between
    MARKER and payload so that decode can separate real payload from random padding.
    When no padding is needed, the format is MARKER + encrypted_payload (identical
    to fastshot FileHyder), ensuring cross-compatibility.

    Args:
        target_size: desired final file size in bytes. 0 = no padding.
                     If smaller than the natural output, padding is skipped.
    """
    tmp = tempfile.mkdtemp(prefix="hyder_")
    try:
        zip_path = os.path.join(tmp, "payload.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            if os.path.isdir(source_path):
                for root, dirs, files in os.walk(source_path):
                    for f in files:
                        abs_path = os.path.join(root, f)
                        rel_path = os.path.relpath(abs_path, os.path.join(source_path, os.pardir))
                        zf.write(abs_path, rel_path)
            else:
                zf.write(source_path, os.path.basename(source_path))

        with open(zip_path, 'rb') as f:
            zip_data = f.read()

        encrypted = xor_bytes(zip_data, key)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"hyd_{ts}.png"
        out_path = os.path.join(output_dir, out_name)

        os.makedirs(output_dir, exist_ok=True)
        shutil.copy2(cover_png, out_path)

        cover_size = os.path.getsize(out_path)
        natural_size = cover_size + len(MARKER) + len(encrypted)

        with open(out_path, 'ab') as f:
            f.write(MARKER)
            if target_size > 0 and target_size > natural_size + 4:
                # Need padding — write length header so decode can skip padding
                len_bytes = xor_bytes(_LEN_STRUCT.pack(len(encrypted)), key)
                f.write(len_bytes)
                f.write(encrypted)
                raw_padding = os.urandom(target_size - natural_size - 4)
                f.write(xor_bytes(raw_padding, key))
            else:
                # No padding — write MARKER + encrypted only (fastshot compatible)
                f.write(encrypted)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return out_path


def encode_text_to_png(text: str, cover_png: str, key: str, output_dir: str,
                       target_size: int = 0) -> str:
    """Write text to a temp .txt, then call encode_to_png."""
    tmp = tempfile.mkdtemp(prefix="hyder_")
    try:
        txt_path = os.path.join(tmp, "content.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        return encode_to_png(txt_path, cover_png, key, output_dir, target_size)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def decode_from_png(png_path: str, key: str, output_dir: str) -> str:
    """Extract encrypted payload from PNG, decrypt and unzip.

    Supports two formats:
      Format 1 (fastshot / legacy): MARKER + XOR-encrypted-zip
      Format 2 (with length header): MARKER + XOR'd-4byte-length + XOR-encrypted-zip [+ padding]
    Detection: after the MARKER, try reading 4 bytes as a length. If the length
    makes sense (points to valid ZIP data), use it. Otherwise fall back to
    treating everything after MARKER as the payload (legacy format).
    """
    with open(png_path, 'rb') as f:
        data = f.read()

    idx = data.find(MARKER)
    if idx == -1:
        raise ValueError("未在 PNG 文件中找到隐藏数据 (缺少 FHDR 标记)")

    after_marker = data[idx + len(MARKER):]
    if not after_marker:
        raise ValueError("PNG 文件中没有隐藏的Codec数据")

    # Try Format 2: 4-byte XOR'd length header then XOR'd payload (+ optional padding)
    # Length header and payload are each independently XOR'd (both start at key index 0).
    payload = None
    if len(after_marker) > 4:
        len_decrypted = xor_bytes(after_marker[:4], key)
        stored_len = _LEN_STRUCT.unpack(len_decrypted)[0]
        # Sanity check: length must be positive, fit in remaining data, and not unreasonably large
        if 0 < stored_len <= len(after_marker) - 4 and stored_len <= 500 * 1024 * 1024:
            candidate = xor_bytes(after_marker[4:4 + stored_len], key)
            if len(candidate) >= 4 and candidate[:4] == b'PK\x03\x04':
                payload = candidate

    # Fallback: Format 1 (legacy / fastshot — no length header)
    if payload is None:
        payload = xor_bytes(after_marker, key)
        if len(payload) < 4 or payload[:4] != b'PK\x03\x04':
            raise ValueError(" Decodex失败 — seed错误或文件已损坏")

    base = os.path.splitext(os.path.basename(png_path))[0]
    folder = os.path.join(output_dir, base)
    os.makedirs(folder, exist_ok=True)

    zip_path = os.path.join(folder, "payload.zip")
    with open(zip_path, 'wb') as f:
        f.write(payload)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(folder)
    except zipfile.BadZipFile:
        shutil.rmtree(folder, ignore_errors=True)
        raise ValueError(" Decodex失败 — seed错误或文件已损坏")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    return folder


def check_png_has_hidden(png_path: str):
    """Check if PNG contains hidden data. Returns (has_hidden, hidden_size)."""
    size = os.path.getsize(png_path)
    with open(png_path, 'rb') as f:
        data = f.read()
    idx = data.find(MARKER)
    if idx == -1:
        return False, 0
    hidden_size = size - idx - len(MARKER)
    return True, hidden_size


# ── GUI ─────────────────────────────────────────────────────────────────────

class HyderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Hyder Tool - PNG Transformation Codec工具")
        self.root.geometry("680x650")
        self.root.resizable(True, True)
        self.root.minsize(580, 520)

        self._build_ui()

    # ── build widgets ──────────────────────────────────────────────────────

    def _build_ui(self):
        pad = dict(padx=8, pady=4)

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        tab_enc = ttk.Frame(nb)
        tab_dec = ttk.Frame(nb)
        nb.add(tab_enc, text="  Encode (Transformation Codec)  ")
        nb.add(tab_dec, text="  Decode (Restore Decodex)  ")

        self._build_encode_tab(tab_enc, pad)
        self._build_decode_tab(tab_dec, pad)

        self._toggle_enc_source()

    # ─── Encode tab ────────────────────────────────────────────────────────

    def _build_encode_tab(self, frm, pad):
        # Source type
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="数据来源:", font=("", 9, "bold")).pack(side=tk.LEFT)
        self.enc_type = tk.StringVar(value="file")
        ttk.Radiobutton(row, text="文件/文件夹", variable=self.enc_type,
                        value="file", command=self._toggle_enc_source).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(row, text="文字内容", variable=self.enc_type,
                        value="text", command=self._toggle_enc_source).pack(side=tk.LEFT, padx=8)

        # File picker row
        self.enc_file_row = ttk.Frame(frm)
        self.enc_file_row.pack(fill=tk.X, **pad)
        ttk.Label(self.enc_file_row, text="选择文件:").pack(side=tk.LEFT)
        self.enc_file_path = tk.StringVar()
        self.enc_file_entry = ttk.Entry(self.enc_file_row, textvariable=self.enc_file_path)
        self.enc_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.enc_file_btn = ttk.Button(self.enc_file_row, text="浏览...", command=self._browse_file)
        self.enc_file_btn.pack(side=tk.LEFT)
        self.enc_folder_btn = ttk.Button(self.enc_file_row, text="文件夹...", command=self._browse_folder)
        self.enc_folder_btn.pack(side=tk.LEFT, padx=(4, 0))
        self.enc_file_info = ttk.Label(self.enc_file_row, text="", foreground="gray")
        self.enc_file_info.pack(side=tk.LEFT, padx=4)

        # Text input
        self.enc_text_row = ttk.Frame(frm)
        self.enc_text_row.pack(fill=tk.BOTH, expand=True, **pad)
        ttk.Label(self.enc_text_row, text="输入文字内容:").pack(anchor=tk.W)
        self.enc_text = scrolledtext.ScrolledText(self.enc_text_row, height=5, wrap=tk.WORD)
        self.enc_text.pack(fill=tk.BOTH, expand=True)

        ttk.Separator(frm, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        # Cover PNG
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="Transformation封面 PNG:", font=("", 9, "bold")).pack(side=tk.LEFT)
        self.enc_cover = tk.StringVar()
        ttk.Entry(row, textvariable=self.enc_cover).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(row, text="浏览...", command=self._browse_cover).pack(side=tk.LEFT)
        self.enc_cover_info = ttk.Label(row, text="", foreground="gray")
        self.enc_cover_info.pack(side=tk.LEFT, padx=4)

        # Encryption key
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=" Codec seed:").pack(side=tk.LEFT)
        self.enc_key = tk.StringVar(value="qwer1234")
        self.enc_key_entry = ttk.Entry(row, textvariable=self.enc_key, show="*")
        self.enc_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.enc_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="显示", variable=self.enc_show,
                        command=lambda: self._toggle_key_vis(self.enc_key_entry, self.enc_show)).pack(side=tk.LEFT)

        # Output dir
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="输出目录:").pack(side=tk.LEFT)
        self.enc_out = tk.StringVar(value=os.path.join(os.getcwd(), "output"))
        ttk.Entry(row, textvariable=self.enc_out).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(row, text="浏览...", command=self._browse_out_dir).pack(side=tk.LEFT)

        # Target file size (padding)
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        self.enc_use_target = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="自定义输出大小:", variable=self.enc_use_target,
                        command=self._toggle_target_size).pack(side=tk.LEFT)
        self.enc_target_size = tk.StringVar(value="200000")
        self.enc_target_entry = ttk.Entry(row, textvariable=self.enc_target_size, width=12,
                                           state=tk.DISABLED)
        self.enc_target_entry.pack(side=tk.LEFT, padx=4)
        ttk.Label(row, text="字节 (填充随机数据至指定大小)", foreground="gray").pack(side=tk.LEFT)

        # Encode button + result
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        self.enc_btn = ttk.Button(row, text="  Encode Transformation Codec  ", command=self._do_encode)
        self.enc_btn.pack(side=tk.LEFT)

        self.enc_result = tk.StringVar()
        ttk.Label(frm, textvariable=self.enc_result, foreground="green",
                  wraplength=640).pack(fill=tk.X, **pad)

    # ─── Decode tab ────────────────────────────────────────────────────────

    def _build_decode_tab(self, frm, pad):
        # PNG file
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="Transformation PNG 文件:", font=("", 9, "bold")).pack(side=tk.LEFT)
        self.dec_png = tk.StringVar()
        ttk.Entry(row, textvariable=self.dec_png).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(row, text="浏览...", command=self._browse_dec_png).pack(side=tk.LEFT)
        self.dec_png_info = ttk.Label(row, text="", foreground="gray")
        self.dec_png_info.pack(side=tk.LEFT, padx=4)

        # Check button
        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, **pad)
        ttk.Button(row2, text="检查文件", command=self._do_check).pack(side=tk.LEFT)

        ttk.Separator(frm, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        # Decryption key
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text=" Decodex seed:").pack(side=tk.LEFT)
        self.dec_key = tk.StringVar(value="qwer1234")
        self.dec_key_entry = ttk.Entry(row, textvariable=self.dec_key, show="*")
        self.dec_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.dec_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="显示", variable=self.dec_show,
                        command=lambda: self._toggle_key_vis(self.dec_key_entry, self.dec_show)).pack(side=tk.LEFT)

        # Output dir
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        ttk.Label(row, text="输出目录:").pack(side=tk.LEFT)
        self.dec_out = tk.StringVar(value=os.path.join(os.getcwd(), "decoded"))
        ttk.Entry(row, textvariable=self.dec_out).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(row, text="浏览...", command=self._browse_dec_out).pack(side=tk.LEFT)

        # Decode buttons
        row = ttk.Frame(frm)
        row.pack(fill=tk.X, **pad)
        self.dec_btn = ttk.Button(row, text="  Decode Restore Decodex  ", command=self._do_decode)
        self.dec_btn.pack(side=tk.LEFT)

        # Status label
        self.dec_result = tk.StringVar()
        self.dec_status_label = ttk.Label(frm, textvariable=self.dec_result, foreground="blue",
                  wraplength=640)
        self.dec_status_label.pack(fill=tk.X, **pad)

        # Result detail area
        ttk.Label(frm, text=" Decodex结果:").pack(anchor=tk.W, padx=8)
        self.dec_detail = scrolledtext.ScrolledText(frm, height=12, wrap=tk.WORD,
                                                     font=("Consolas", 9), state=tk.DISABLED)
        self.dec_detail.pack(fill=tk.BOTH, expand=True, **pad)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _toggle_enc_source(self):
        is_file = self.enc_type.get() == "file"
        if is_file:
            self.enc_text.config(state=tk.DISABLED)
            self.enc_file_entry.config(state=tk.NORMAL)
            self.enc_file_btn.config(state=tk.NORMAL)
            self.enc_folder_btn.config(state=tk.NORMAL)
        else:
            self.enc_text.config(state=tk.NORMAL)
            self.enc_file_entry.config(state=tk.DISABLED)
            self.enc_file_btn.config(state=tk.DISABLED)
            self.enc_folder_btn.config(state=tk.DISABLED)

    @staticmethod
    def _toggle_key_vis(entry: ttk.Entry, show: tk.BooleanVar):
        entry.config(show="" if show.get() else "*")

    def _toggle_target_size(self):
        state = tk.NORMAL if self.enc_use_target.get() else tk.DISABLED
        self.enc_target_entry.config(state=state)

    def _browse_file(self):
        p = filedialog.askopenfilename(title="选择要Transformation的文件")
        if p:
            self.enc_file_path.set(p)
            size_kb = os.path.getsize(p) / 1024
            self.enc_file_info.config(text=f"{size_kb:.1f} KB")

    def _browse_folder(self):
        p = filedialog.askdirectory(title="选择要Transformation的文件夹")
        if p:
            self.enc_file_path.set(p)
            total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(p) for f in fns)
            self.enc_file_info.config(text=f"文件夹 {total / 1024:.1f} KB")

    def _browse_cover(self):
        p = filedialog.askopenfilename(title="选择Transformation用的 PNG 图片",
                                       filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if p:
            self.enc_cover.set(p)
            size_kb = os.path.getsize(p) / 1024
            has_hidden, _ = check_png_has_hidden(p)
            if has_hidden:
                self.enc_cover_info.config(text=f"{size_kb:.1f} KB (已含隐藏数据)", foreground="orange")
            else:
                self.enc_cover_info.config(text=f"{size_kb:.1f} KB", foreground="gray")

    def _browse_out_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.enc_out.set(d)

    def _browse_dec_png(self):
        p = filedialog.askopenfilename(title="选择Transformation PNG 文件",
                                       filetypes=[("PNG images", "*.png"), ("All files", "*.*")])
        if p:
            self.dec_png.set(p)
            size_kb = os.path.getsize(p) / 1024
            has_hidden, hidden_size = check_png_has_hidden(p)
            if has_hidden:
                self.dec_png_info.config(
                    text=f"{size_kb:.1f} KB | 隐藏数据 {hidden_size / 1024:.1f} KB", foreground="green")
            else:
                self.dec_png_info.config(text=f"{size_kb:.1f} KB | 无隐藏数据", foreground="red")

    def _browse_dec_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.dec_out.set(d)

    # ── actions ─────────────────────────────────────────────────────────────

    def _do_encode(self):
        cover = self.enc_cover.get().strip()
        if not cover or not os.path.isfile(cover):
            messagebox.showerror("错误", "请选择有效的Transformation PNG 图片")
            return

        key = self.enc_key.get().strip()
        if not key:
            messagebox.showerror("错误", "请输入 Codec seed")
            return

        out_dir = self.enc_out.get().strip()
        if not out_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return

        self.enc_btn.config(state=tk.DISABLED)
        self.enc_result.set("处理中...")
        self.root.update()

        # Parse optional target size
        target_size = 0
        if self.enc_use_target.get():
            try:
                target_size = int(self.enc_target_size.get().strip())
                if target_size <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("错误", "目标文件大小必须为正整数")
                self.enc_btn.config(state=tk.NORMAL)
                return

        try:
            if self.enc_type.get() == "file":
                src = self.enc_file_path.get().strip()
                if not src or not os.path.exists(src):
                    messagebox.showerror("错误", "请选择有效的文件或文件夹")
                    return
                result = encode_to_png(src, cover, key, out_dir, target_size)
            else:
                text = self.enc_text.get("1.0", tk.END).strip()
                if not text:
                    messagebox.showerror("错误", "请输入要Transformation的文字内容")
                    return
                result = encode_text_to_png(text, cover, key, out_dir, target_size)

            out_size = os.path.getsize(result) / 1024
            self.enc_result.set(f"成功! 输出: {result}  ({out_size:.1f} KB)")

            if messagebox.askyesno("完成", f"Transformation Codec完成!\n\n{result}\n\n是否打开输出文件夹?"):
                os.startfile(os.path.dirname(result))
        except Exception as e:
            messagebox.showerror("Encode 失败", str(e))
            self.enc_result.set("")
        finally:
            self.enc_btn.config(state=tk.NORMAL)

    def _do_check(self):
        png = self.dec_png.get().strip()
        if not png or not os.path.isfile(png):
            messagebox.showerror("错误", "请选择有效的 PNG 文件")
            return

        has_hidden, hidden_size = check_png_has_hidden(png)
        size_kb = os.path.getsize(png) / 1024

        self.dec_detail.config(state=tk.NORMAL)
        self.dec_detail.delete("1.0", tk.END)

        info = f"文件: {png}\n"
        info += f"大小: {size_kb:.1f} KB\n"
        info += f"隐藏数据: {'是' if has_hidden else '否'}\n"
        if has_hidden:
            info += f"隐藏数据大小 ( Codec后): {hidden_size / 1024:.1f} KB\n"
            info += "\n该文件包含隐藏数据，可尝试使用正确的 seed Decodex。"
        else:
            info += "\n该文件不包含 FHDR 标记的隐藏数据。"

        self.dec_detail.insert("1.0", info)
        self.dec_detail.config(state=tk.DISABLED)

    def _do_decode(self):
        png = self.dec_png.get().strip()
        if not png or not os.path.isfile(png):
            messagebox.showerror("错误", "请选择有效的 PNG 文件")
            return

        key = self.dec_key.get().strip()
        if not key:
            messagebox.showerror("错误", "请输入 Decodex seed")
            return

        out_dir = self.dec_out.get().strip()
        if not out_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return

        self.dec_btn.config(state=tk.DISABLED)
        self.dec_result.set("正在 Decodex...")
        self.dec_status_label.config(foreground="blue")
        self.root.update()

        try:
            result_dir = decode_from_png(png, key, out_dir)
            self.dec_result.set(f"成功! 输出: {result_dir}")
            self.dec_status_label.config(foreground="green")

            # Show extracted contents
            contents = []
            for root, dirs, files in os.walk(result_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, result_dir)
                    size = os.path.getsize(fp)
                    contents.append(f"  {rel}  ({size} bytes)")

            detail = f" Decodex完成!\n"
            detail += f"输出目录: {result_dir}\n"
            detail += f"提取文件 ({len(contents)} 个):\n"
            detail += "\n".join(contents)

            # Preview text files
            for root, dirs, files in os.walk(result_dir):
                for f in files:
                    if f.endswith('.txt'):
                        fp = os.path.join(root, f)
                        try:
                            with open(fp, 'r', encoding='utf-8') as tf:
                                preview = tf.read(500)
                            detail += f"\n\n--- {f} 预览 ---\n{preview}"
                            if len(preview) >= 500:
                                detail += "\n... (更多内容请查看完整文件)"
                        except Exception:
                            pass

            self.dec_detail.config(state=tk.NORMAL)
            self.dec_detail.delete("1.0", tk.END)
            self.dec_detail.insert("1.0", detail)
            self.dec_detail.config(state=tk.DISABLED)

            if messagebox.askyesno("完成", f"Restore Decodex完成!\n\n输出: {result_dir}\n\n是否打开输出文件夹?"):
                os.startfile(result_dir)
        except Exception as e:
            messagebox.showerror("Decode 失败", str(e))
            self.dec_result.set(f"失败: {e}")
            self.dec_status_label.config(foreground="red")
        finally:
            self.dec_btn.config(state=tk.NORMAL)


# ── main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = HyderApp(root)
    root.mainloop()
