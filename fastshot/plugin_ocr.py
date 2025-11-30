from rapidocr import RapidOCR, EngineType
from PIL import Image
import win32clipboard
import tkinter as tk
import numpy as np
import os

class PluginOCR:
    def __init__(self):
        # Get the path to bundled models
        resources_dir = os.path.join(os.path.dirname(__file__), "resources")
        det_model_path = os.path.join(resources_dir, "ch_PP-OCRv5_mobile_det.onnx")
        rec_model_path = os.path.join(resources_dir, "ch_PP-OCRv5_rec_mobile_infer.onnx")

        # Use RapidOCR with bundled PP-OCRv5 models (no network required)
        self.ocr_engine = RapidOCR(
            params={
                "Det.engine_type": EngineType.ONNXRUNTIME,
                "Det.model_path": det_model_path,
                "Rec.engine_type": EngineType.ONNXRUNTIME,
                "Rec.model_path": rec_model_path,
            }
        )

    def ocr(self, image):
        # RapidOCR accepts: str path, np.ndarray, bytes, or Path
        if isinstance(image, Image.Image):
            image = np.array(image)

        result = self.ocr_engine(image)

        # Extract text from RapidOCR result and merge lines
        # RapidOCROutput has attributes: boxes, txts, scores
        ocr_text = ""
        if result and result.boxes is not None and result.txts is not None:
            try:
                ocr_text = self._merge_text_lines(result.boxes, result.txts)
            except Exception as e:
                ocr_text = f"OCR Error: {e}"

        self.copy_to_clipboard(ocr_text)
        return ocr_text

    def _merge_text_lines(self, boxes, txts):
        """
        Merge OCR results into lines based on bounding box positions.
        Groups text blocks on the same horizontal line, sorts left to right.
        """
        if boxes is None or txts is None or len(boxes) == 0 or len(txts) == 0:
            return ""

        # Calculate box info: (center_y, height, min_x, max_x, txt)
        items = []
        for box, txt in zip(boxes, txts):
            # box: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            box = list(box)  # Convert numpy array to list if needed
            ys = [float(p[1]) for p in box]
            xs = [float(p[0]) for p in box]
            min_y, max_y = min(ys), max(ys)
            min_x, max_x = min(xs), max(xs)
            center_y = (min_y + max_y) / 2
            height = max_y - min_y
            items.append({
                'center_y': center_y,
                'height': height,
                'min_x': min_x,
                'max_x': max_x,
                'txt': txt
            })

        # Sort by center_y first (top to bottom)
        items.sort(key=lambda x: x['center_y'])

        # Group items into lines based on y-coordinate overlap
        lines = []
        used = [False] * len(items)

        for i, item in enumerate(items):
            if used[i]:
                continue

            # Start a new line with this item
            line = [item]
            used[i] = True

            # Line threshold: use median height of current line items
            line_y = item['center_y']
            threshold = item['height'] * 0.5  # Allow 50% height overlap

            # Find all items on the same line
            for j in range(i + 1, len(items)):
                if used[j]:
                    continue

                # Check if item j is on the same line
                if abs(items[j]['center_y'] - line_y) <= threshold:
                    line.append(items[j])
                    used[j] = True
                    # Update line_y to average of all items in line
                    line_y = sum(it['center_y'] for it in line) / len(line)
                    # Update threshold based on max height in line
                    threshold = max(it['height'] for it in line) * 0.5

            lines.append(line)

        # Sort each line left to right, then join with spaces
        result_lines = []
        for line in lines:
            line.sort(key=lambda x: x['min_x'])
            line_text = ' '.join(item['txt'] for item in line)
            result_lines.append(line_text)

        return '\n'.join(result_lines)

    def copy_to_clipboard(self, text):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()

    def show_message(self, message, parent):
        label = tk.Label(parent, text=message, bg="yellow", fg="black", font=("Helvetica", 10))
        label.pack(side="bottom", fill="x")
        parent.after(3000, label.destroy)
