# fastshot/notes_sync.py

import json
import io
import configparser
import os
from datetime import datetime
from PIL import Image

try:
    import requests
except ImportError:
    requests = None


class NotesSyncManager:
    """Syncs encrypted session data to Siyuan Wrapper via /webhook/fastshot/en.

    Uses the same XOR + FHDR steganography as cloud_sync.py / hyder_tool_app.py,
    ensuring the Wrapper can decrypt the payload.
    """

    MARKER = b'FHDR'

    def __init__(self, app):
        self.app = app
        self.wrapper_url = ''
        self.encryption_key = ''
        self._enabled = False
        self._load_config()

    def _load_config(self):
        """Read [NotesSync] section from config.ini."""
        try:
            config = self.app.config
            if config.has_section('NotesSync'):
                self.wrapper_url = config.get('NotesSync', 'wrapper_url', fallback='').strip()
                self.encryption_key = config.get('NotesSync', 'encryption_key', fallback='').strip()
                self._enabled = config.getboolean('NotesSync', 'notes_sync_enabled', fallback=False)
            else:
                self._enabled = False
        except Exception as e:
            print(f"[NotesSync] Error loading config: {e}")
            self._enabled = False

        # Enable only when all required fields are present
        if self._enabled and (not self.wrapper_url or not self.encryption_key):
            print("[NotesSync] wrapper_url or enc_key missing, disabled")
            self._enabled = False

        print(f"[NotesSync] enabled={self._enabled}, url={self.wrapper_url or '(not set)'}")

    @property
    def notes_sync_enabled(self):
        return self._enabled

    # ---------------------------------------------------------------- crypto

    def _encrypt_data(self, data: bytes) -> bytes:
        """XOR encrypt — symmetric, identical to cloud_sync._encrypt_data."""
        if not self.encryption_key:
            return data
        key_bytes = self.encryption_key.encode()
        key_len = len(key_bytes)
        out = bytearray(len(data))
        for i, b in enumerate(data):
            out[i] = b ^ key_bytes[i % key_len]
        return bytes(out)

    def _disguise_in_image(self, data: bytes) -> bytes:
        """Append encrypted data after a cover PNG with FHDR marker.

        Same format as cloud_sync._disguise_in_image and hyder_tool_app:
            [valid PNG bytes] [FHDR] [encrypted payload]
        """
        try:
            cover_path = os.path.join(os.path.dirname(__file__), 'resources', 'cover.png')
            if os.path.exists(cover_path):
                with open(cover_path, 'rb') as f:
                    png_bytes = f.read()
                print(f"[NotesSync] Using cover.png ({len(png_bytes)} bytes)")
            else:
                print(f"[NotesSync] cover.png not found at {cover_path}, fallback to blank")
                img = Image.new('RGB', (100, 100), color='white')
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                png_bytes = buf.getvalue()
            return png_bytes + self.MARKER + data
        except Exception as e:
            print(f"[NotesSync] Error disguising data: {e}")
            return data

    # ------------------------------------------------------------ public API

    def save_session_to_notes(self, session_data: dict, metadata: dict,
                              progress_callback=None) -> str:
        """Encrypt, disguise, and POST session to Siyuan Wrapper.

        Args:
            session_data: The 'session' dict from _prepare_session_data().
            metadata: Dict with name, desc, tags, color, class.
            progress_callback: callable(progress_pct, message).

        Returns:
            The session filename on success.

        Raises:
            Exception on any failure.
        """
        if requests is None:
            raise Exception("requests library not installed")

        if not self._enabled:
            raise Exception("Notes sync is not enabled")

        if progress_callback:
            progress_callback(0, "Preparing session data...")

        # Build full session payload (same structure as cloud_sync)
        from .session_manager import SessionManager, ThumbnailCreator

        # Create thumbnail
        images = []
        for w in session_data.get('windows', []):
            img_data = w.get('original_image_data')
            if img_data:
                img = SessionManager.deserialize_image_static(img_data)
                if img:
                    images.append(img)

        thumbnail_data = None
        if images:
            collage = ThumbnailCreator.create_thumbnail_collage(images)
            if collage:
                thumbnail_data = SessionManager.serialize_image_static(collage)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        name = metadata.get('name', '')
        if name.strip():
            safe_name = "".join(c for c in name[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{timestamp}_{safe_name}.fastshot"
        else:
            filename = f"{timestamp}_notes_session.fastshot"

        full_session = {
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
                'thumbnail_collage': thumbnail_data,
            }
        }

        if progress_callback:
            progress_callback(30, "encoding session data...")

        # JSON → bytes
        json_bytes = json.dumps(full_session, ensure_ascii=False).encode('utf-8')
        print(f"[NotesSync] Session JSON size: {len(json_bytes)} bytes")

        # Encrypt
        encrypted = self._encrypt_data(json_bytes)
        print(f"[NotesSync] XOR encoded ({self.encryption_key[:2]}***), size: {len(encrypted)} bytes")

        if progress_callback:
            progress_callback(50, "Disguising as image...")

        # Disguise
        disguised = self._disguise_in_image(encrypted)
        print(f"[NotesSync] fill as PNG (cover.png + FHDR marker), size: {len(disguised)} bytes")

        if progress_callback:
            progress_callback(70, "sync to Siyuan Wrapper...")

        # POST multipart
        files = {
            'file': (filename, disguised, 'image/png'),
        }
        data = {}
        # Optionally send key in form data (Wrapper can use config key instead)
        # data['key'] = self.encryption_key

        print(f"[NotesSync] POST {self.wrapper_url}, file={filename} ({len(disguised)} bytes)")
        resp = requests.post(
            self.wrapper_url,
            files=files,
            data=data,
            timeout=60,
        )

        if progress_callback:
            progress_callback(90, "Processing response...")

        if resp.status_code != 200:
            print(f"[NotesSync] Server error: {resp.status_code} - {resp.text[:200]}")
            raise Exception(f"Server returned {resp.status_code}: {resp.text[:200]}")

        print(f"[NotesSync] sync successful: {resp.status_code} - {resp.text[:200]}")

        if progress_callback:
            progress_callback(100, "Notes sync completed!")

        return filename
