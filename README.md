# Fastshot

Fastshot is an open-source Python-based screenshot tool for Windows, inspired by Snipaste. It provides a versatile and user-friendly interface for capturing and annotating screenshots, making it ideal for research, reading papers, writing code, and various comparison and demonstration scenarios.

## Features

- **Always on Top**: Screenshots stay on top, allowing easy comparison.
- **Smooth Zoom and Drag**: Effortlessly zoom and drag screenshots.
- **Annotation Tools**: Hand-drawing and text mode for annotations.
- **Clipboard Export**: Easily export screenshots to the clipboard.
- **OCR Integration**: Extract text from images using the built-in OCR plugin powered by PaddleOCR.

## Installation

You can install Fastshot from PyPI:

```sh
pip install fastshot
```


## Usage
Once installed, you can start Fastshot from the command line:

```sh
fastshot
```

## Hotkeys
`Ctrl+F1`: Activate screen capturing mode.

`Ctrl+P`: Activate paint mode.

`Ctrl+T`: Activate text mode.

`Esc`: Exit the current mode.

## Right-Click Menu

`❌ Close`: Close the current window.

`💾 Save As...`: Save the current screenshot.

`🖌️ Paint`: Activate paint mode.

`↩️ Undo`: Undo the last action.

`🚪 Exit Edit`: Exit paint or text mode.

`📋 Copy`: Copy the current screenshot to the clipboard.

`🔤 Text`: Activate text mode.

🔍 OCR: Perform OCR on the current screenshot and copy the result to the clipboard.


## Plugin Development

Fastshot supports a plugin mechanism that allows developers to extend its functionality. Here is a brief description of how to develop a plugin:


1. **Create a Plugin Class**: Your plugin should be a Python class with the desired functionality. For example, an OCR plugin might look like this:

    ```python
    from paddleocr import PaddleOCR
    from PIL import Image
    import win32clipboard
    import tkinter as tk

    class PluginOCR:
        def __init__(self):
            self.ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')

        def ocr(self, image):
            result = self.ocr_engine.ocr(image, cls=True)
            ocr_text = "\n".join([line[1][0] for res in result for line in res])
            self.copy_to_clipboard(ocr_text)
            return ocr_text

        def copy_to_clipboard(self, text):
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()

        def show_message(self, message, parent):
            label = tk.Label(parent, text=message, bg="yellow", fg="black", font=("Helvetica", 10))
            label.pack(side="bottom", fill="x")
            parent.after(3000, label.destroy)
    ```

2. **Register the Plugin**: In the `SnipasteApp` class, you can register your plugin by adding it to the plugin list.

    ```python
    class SnipasteApp:
        def load_plugins(self):
            plugin_modules = ['fastshot.plugin_ocr']  # Add your plugin module here
            for module_name in plugin_modules:
                module = importlib.import_module(module_name)
                plugin_class = getattr(module, 'PluginOCR')
                self.plugins[module_name] = plugin_class()
    ```

3. **Invoke the Plugin**: You can invoke the plugin from your application code, such as from a menu item.

    ```python
    def ocr(self):
        plugin = self.app.plugins.get('fastshot.plugin_ocr')
        if plugin:
            img_path = 'temp.png'
            self.img_label.zoomed_image.save(img_path)
            result = plugin.ocr(img_path)
            plugin.show_message("OCR result updated in clipboard", self.img_window)
    ```

By following these steps, you can create and integrate custom plugins to extend the functionality of Fastshot.

## Development

### Setting Up the Development Environment

1. Clone the repository:

```sh
git clone https://github.com/yourusername/fastshot.git
cd fastshot
```

2. Install the dependencies:

```sh
pip install -r requirements.txt
```

### Running Tests

You can run the tests using:

```sh
pytest tests/
```

## Contributing
We welcome contributions! Please read our Contributing Guidelines for more details.

## License
This project is licensed under the Apache License - see the LICENSE file for details.

## Todo:
1. ~~tk window force trigger ~~
2. ~~ppocr[Default]~~
3. ~~screenpen integration~~
4. hyder
5. ~~transprent window~~
6. ~~fixed on top~~
7. pyinstaller.
8. gdt-4o multimodal task(OCR/QA)
9. UI(PySimpleGUI/WebPortal)




