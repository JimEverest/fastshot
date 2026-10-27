# fastshot/notes_sync.py

import json
import io
import time
import uuid
import os
from datetime import datetime
from PIL import Image

try:
    import requests
except ImportError:
    requests = None


class NotesSyncManager:
    """Submit a saved session to LifeOS via the unified `/ingest` endpoint.

    Wire format (LifeOS Ingestion Contract v2): the whole capture is ONE JSON
    object (markdown + images-as-base64 + meta), XOR-obfuscated and hidden inside
    a real PNG using the FileHyder format ([cover PNG][FHDR][xor(payload)]) — the
    same envelope cloud_sync.py / hyder_tool_app.py use. It is uploaded as a single
    multipart `file` part, authenticated with a Bearer API key header.

    Two independent secrets, both from config.ini [NotesSync]:
      - api_key         → Authorization: Bearer <api_key>   (authentication)
      - encryption_key  → the XOR key for the envelope       (obfuscation)
    They are different strings; keep each exact (case matters).

    The legacy `/webhook/fastshot/en` path and its Fastshot-specific
    {session, metadata} body are retired; LifeOS organizes/indexes server-side.
    """

    MARKER = b'FHDR'
    DEFAULT_INGEST_URL = "https://json-validator.centralindia.cloudapp.azure.com/ingest"

    def __init__(self, app):
        self.app = app
        self.ingest_url = ''
        self.api_key = ''
        self.encryption_key = ''
        self._enabled = False
        self._load_config()

    def _load_config(self):
        """Read [NotesSync] section from config.ini."""
        try:
            config = self.app.config
            if config.has_section('NotesSync'):
                self.ingest_url = config.get('NotesSync', 'ingest_url', fallback='').strip()
                # Back-compat: fall back to the old wrapper_url key if ingest_url unset.
                if not self.ingest_url:
                    self.ingest_url = config.get('NotesSync', 'wrapper_url', fallback='').strip()
                self.api_key = config.get('NotesSync', 'api_key', fallback='').strip()
                self.encryption_key = config.get('NotesSync', 'encryption_key', fallback='').strip()
                self._enabled = config.getboolean('NotesSync', 'notes_sync_enabled', fallback=False)
            else:
                self._enabled = False
        except Exception as e:
            print(f"[NotesSync] Error loading config: {e}")
            self._enabled = False

        if not self.ingest_url:
            self.ingest_url = self.DEFAULT_INGEST_URL

        # Enable only when all required fields are present.
        if self._enabled and (not self.ingest_url or not self.api_key or not self.encryption_key):
            print("[NotesSync] ingest_url / api_key / encryption_key missing, disabled")
            self._enabled = False

        print(f"[NotesSync] enabled={self._enabled}, url={self.ingest_url or '(not set)'}")

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

        Format (shared with cloud_sync / hyder_tool_app):
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

    # ------------------------------------------------------------ payload

    @staticmethod
    def _best_image_b64(window: dict):
        """Best-quality image for a window, as the already-base64 PNG string.

        Fallback chain mirrors the legacy server: annotated original (100% + marks)
        > original (no marks) > current zoomed.
        """
        return (window.get('annotated_original_data')
                or window.get('original_image_data')
                or window.get('image_data'))

    def _build_capture(self, session_data: dict, metadata: dict, client_msg_id: str) -> dict:
        """Turn a Fastshot session into the LifeOS contract-v2 inner JSON.

        Each window becomes one image (base64 in `images[]`) referenced from the
        Markdown body as `![](shot_NN.png)`.
        """
        windows = session_data.get('windows', []) or []
        images = []
        refs = []
        for i, w in enumerate(windows, start=1):
            b64 = self._best_image_b64(w)
            if not b64:
                continue
            name = f"shot_{i:02d}.png"
            images.append({"filename": name, "mime_type": "image/png", "data_base64": b64})
            refs.append(f"![]({name})")

        name = (metadata.get('name') or '').strip()
        desc = (metadata.get('desc') or '').strip()
        tags = metadata.get('tags', []) or []
        klass = (metadata.get('class') or '').strip()

        lines = [f"# {name or 'Fastshot capture'}", ""]
        if desc:
            lines += [desc, ""]
        info = []
        if tags:
            info.append("**Tags**: " + ", ".join(str(t) for t in tags))
        if klass:
            info.append("**Class**: " + klass)
        info.append(f"**Images**: {len(images)}")
        lines += info + [""]
        lines += refs
        content_markdown = "\n".join(lines) + "\n"

        return {
            "source": "fastshot",
            "client_msg_id": client_msg_id,
            "title": name or f"Fastshot {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().astimezone().isoformat(),
            "content_markdown": content_markdown,
            "tags": [str(t) for t in tags],
            "participants": [],
            "meta": {
                "client": "fastshot",
                "desc": desc,
                "color": metadata.get('color', 'blue'),
                "class": klass,
                "image_count": len(images),
            },
            "images": images,
        }

    # ------------------------------------------------------------ public API

    def save_session_to_notes(self, session_data: dict, metadata: dict,
                              progress_callback=None) -> str:
        """Encrypt, disguise, and POST a session to LifeOS `/ingest`.

        Args:
            session_data: The dict from SessionManager._prepare_session_data().
            metadata: Dict with name, desc, tags, color, class.
            progress_callback: callable(progress_pct, message).

        Returns:
            A display filename on success.

        Raises:
            Exception on any failure.
        """
        if requests is None:
            raise Exception("requests library not installed")
        if not self._enabled:
            raise Exception("Notes sync is not enabled")

        if progress_callback:
            progress_callback(0, "Preparing session data...")

        # Stable idempotency key for this save (reused across retries → no dup note).
        client_msg_id = uuid.uuid4().hex

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        name = (metadata.get('name') or '').strip()
        if name:
            safe_name = "".join(c for c in name[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"{timestamp}_{safe_name}.fastshot"
        else:
            filename = f"{timestamp}_notes_session.fastshot"

        capture = self._build_capture(session_data, metadata, client_msg_id)
        if not capture["images"]:
            raise Exception("No image windows to submit")

        if progress_callback:
            progress_callback(30, "Encoding capture...")

        # JSON → bytes → XOR → disguise as PNG (FileHyder envelope).
        json_bytes = json.dumps(capture, ensure_ascii=False).encode('utf-8')
        print(f"[NotesSync] capture JSON size: {len(json_bytes)} bytes, images={len(capture['images'])}")
        encrypted = self._encrypt_data(json_bytes)

        if progress_callback:
            progress_callback(50, "Disguising as image...")
        disguised = self._disguise_in_image(encrypted)
        print(f"[NotesSync] envelope size: {len(disguised)} bytes (cover.png + FHDR + XOR)")

        if progress_callback:
            progress_callback(70, "Submitting to LifeOS...")

        files = {'file': (f"{timestamp}.png", disguised, 'image/png')}
        headers = {'Authorization': f'Bearer {self.api_key}'}

        # Honor the contract's retry guidance: reuse the same client_msg_id so a
        # network/5xx retry is idempotent (server returns the same doc_id).
        print(f"[NotesSync] POST {self.ingest_url} ({len(disguised)} bytes)")
        last_err = None
        for attempt, delay in enumerate(((0, 1), (1, 4), (2, 0)), start=0):
            try:
                resp = requests.post(self.ingest_url, files=files, headers=headers, timeout=60)
            except Exception as e:
                last_err = f"network error: {e}"
                print(f"[NotesSync] {last_err} (attempt {attempt})")
                if delay[1]:
                    time.sleep(delay[1])
                continue

            if resp.status_code == 200:
                try:
                    body = resp.json()
                except Exception:
                    body = {}
                doc_id = body.get('doc_id', '?')
                deduped = body.get('deduped')
                print(f"[NotesSync] OK doc_id={doc_id} deduped={deduped} assets={body.get('assets')}")
                if progress_callback:
                    progress_callback(100, "Submitted to LifeOS!")
                return filename

            # Parse the stable error code; never echo note text.
            code = None
            try:
                code = (resp.json() or {}).get('detail', {}).get('code')
            except Exception:
                pass
            # 4xx are permanent for this payload → do not retry.
            if 400 <= resp.status_code < 500:
                raise Exception(f"{resp.status_code} {code or resp.text[:120]}")
            last_err = f"{resp.status_code} {code or resp.text[:120]}"
            print(f"[NotesSync] server {last_err} (attempt {attempt})")
            if delay[1]:
                time.sleep(delay[1])

        raise Exception(f"Submit failed after retries: {last_err}")
