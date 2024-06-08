# Fastshot

Fastshot is a versatile screen capturing tool that allows users to take screenshots, annotate them with paint and text tools, and perform OCR (Optical Character Recognition) to extract text from images. The application provides an intuitive interface and can be extended with plugins.

## Features

- **Screen Capturing**: Capture any part of your screen using a customizable hotkey.
- **Annotation Tools**: Use paint and text tools to annotate your screenshots.
- **OCR Integration**: Extract text from images using the built-in OCR plugin powered by PaddleOCR.
- **Plugin System**: Easily extend the functionality with plugins.

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
F1: Activate screen capturing mode.

Ctrl+P: Activate paint mode.

Ctrl+T: Activate text mode.

Esc: Exit the current mode.

## Right-Click Menu

Close: Close the current window.

Save As...: Save the current screenshot.

Paint: Activate paint mode.

Undo: Undo the last action.

Exit Edit: Exit paint or text mode.

Copy: Copy the current screenshot to the clipboard.

Text: Activate text mode.

OCR: Perform OCR on the current screenshot and copy the result to the clipboard.


## Development
Setting Up the Development Environment
1. Clone the repository:

```sh
git clone https://github.com/yourusername/fastshot.git
cd fastshot
```

2. Install the dependencies:
```sh
pip install -r requirements.txt
```

## Running Tests
You can run the tests using:

```sh
pytest tests/
```

## Contributing
We welcome contributions! Please read our Contributing Guidelines for more details.

## License
This project is licensed under the Apache License - see the LICENSE file for details.





