# Fastshot

Fastshot is a GenAI powered screenshot and annotation tool designed to optimize your workflow. Ideal for students, developers, researchers, and operations professionals, Fastshot enhances multitasking by providing seamless, efficient tools to capture, pin, annotate, and analyze screen content.

With its "pin on top" feature, Fastshot allows users to keep screenshots easily accessible while enabling smooth zooming, moving, annotation, and copying for multi-system comparisons. The built-in OCR tool enables quick extraction of text from any part of the screen, further streamlining your workflow.

Additionally, Fastshot’s GenAI-powered assistant offers advanced analysis and summarization of screen content, allowing users to extract information and ask questions with ease, significantly boosting productivity.

The tool also includes a Screen Pen feature, window pinning capabilities, and customizable window opacity adjustments—perfect for managing complex workflows across multiple windows and tasks.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Shortcuts](#shortcuts)
- [Plugin Mechanism](#plugin-mechanism)
- [Who Can Benefit](#who-can-benefit)
  - [Students](#students)
  - [Developers](#developers)
  - [Researchers](#researchers)
  - [Operations Personnel](#operations-personnel)
- [Contributing](#contributing)
- [License](#license)


## Features

### Screenshot and Annotation
- **Always on Top**: Keep screenshots above all other windows for easy comparison.
- **Smooth Zoom and Drag**: Effortlessly zoom and drag screenshots to focus on details.
- **Annotation Tools**: Hand-drawing and text mode for quick annotations.
- **Clipboard Export**: Easily export screenshots to the clipboard for sharing.
- **OCR Integration**: Extract text from images using the built-in OCR plugin powered by PaddleOCR running locally.
- **AI Assistant**: Ask questions about the screenshot using the integrated GenAI assistant.

### Context Menu Options
- ❌ **Close**: Close the current window.
- 💾 **Save As...**: Save the current screenshot.
- 🖌️ **Paint**: Activate paint mode for freehand drawing.
- ↩️ **Undo**: Undo the last action.
- 🚪 **Exit Edit**: Exit paint or text mode.
- 📋 **Copy**: Copy the current screenshot to the clipboard.
- 🔤 **Text**: Activate text mode to add text annotations.
- 🔍 **OCR**: Perform OCR on the current screenshot and copy the result to the clipboard.

### System Window Control
- 📌 **Always on Top**: Toggle the window's always-on-top state.
- 🔍 **Window Transparency Adjustment**: Adjust transparency of any system window via hotkeys for better multitasking.

### Screen Annotation
- 🖊️ **Screen Pen**: Activate the screen pen to annotate anywhere on your screen.

### GenAI Assistant
- **Multimodal AI Assistant**: Seamlessly integrated AI assistant that can read any content on your screen and answer your questions.

## Installation

You can install Fastshot from PyPI:

```bash
pip install fastshot
```


## Usage
Once installed, you can start Fastshot from the command line:
```bash
fastshot
```

## LLM Env Variable  (2 way)

### OpenAI Standard:
```bash
setx OPENAI_TOKEN "sk-kK"
setx OPENAI_MM_URL "https://xxx"
setx OPENAI_CHATGPT_URL "https://xxx"
setx HEAD_TOKEN_KEY "Authorization"
```
### Standalone Token Exchange:
```bash
setx OPENAI_TOKEN_URL ""
setx OPENAI_USER_NAME ""
setx OPENAI_PASSWORD ""
setx OPENAI_APPLICATION_ID ""
setx OPENAI_APPLICATION_NAME ""
setx OPENAI_MM_URL "https://xxx"
setx OPENAI_CHATGPT_URL "https://xxx"
setx HEAD_TOKEN_KEY "Authorization"

setx OPENAI_HEALTH_URL ""
```

## Shortcuts
Customize your experience with configurable shortcuts. Most operations require only a single hotkey, minimizing the need for repetitive touch points.

![Shortcuts](./shortcuts.png)

```ini
[Shortcuts]
hotkey_snip = <shift>+a+s
hotkey_paint = <ctrl>+p
hotkey_text = <ctrl>+t

hotkey_screenpen_toggle = <ctrl>+<cmd>+<alt>
hotkey_undo = <ctrl>+z
hotkey_redo = <ctrl>+y
hotkey_screenpen_exit = <esc>
hotkey_screenpen_clear_hide = <ctrl>+<esc>

hotkey_topmost_on = <esc>+`
hotkey_topmost_off = <cmd>+<shift>+\

hotkey_opacity_down = <left>+<right>+<down>
hotkey_opacity_up = <left>+<right>+<up>

[ScreenPen]
enable_screenpen = True
pen_color = red
pen_width = 3
```


## Who Can Benefit

### Students
- **Note-Taking**: Quickly capture and annotate lecture slides or online resources.
- **Collaboration**: Share annotated screenshots with classmates for group projects.
- **Study Aid**: Study Aid: Use the OCR feature to extract text from images for easier studying.
- **7x24 Teacher**: Use the Multimodal GenAI feature to play as a teacher, ask any question that confused you.


### Developers
- **Debugging**: Capture error messages and annotate code snippets.
- **Documentation**: Create annotated screenshots for documentation or tutorials.
- **Multitasking**: Keep reference materials always on top while coding.
- **Coding Copilot**: Generate code directly based on the diagram or UI Design.


### Researchers
- **Data Collection**: Capture and annotate data from various sources.
- **Multi Reference Reading**: Read through multiple Reference paper at the same time.
- **Analysis**: Use the AI assistant to interpret complex diagrams or charts.
- **Organization**: Quickly extract text from images to compile research notes.

### Operations Personnel
- **Efficiency**: Reduce the need for frequent window switching with always-on-top screenshots.
- **Quality Assurance**: Annotate and compare data across different systems.
- **Data Entry:**: Use OCR to minimize manual data entry errors.
- **Decision Making**: Quickly locate key elements in free-format documents.


## Development
### Setting Up the Development Environment
1. Clone the repository:
```bash
git clone https://github.com/jimeverest/fastshot.git
cd fastshot
```
2. Install the dependencies:
```bash
pip install -r requirements.txt
```

### Running Tests
You can run the tests using:
```bash
pytest tests/
```

## Contributing
We welcome contributions from the community! Please read our Contributing Guide to learn how you can help improve Fastshot.

## License
Fastshot is released under the MIT License.

## How Fastshot Enhances Multitasking
Fastshot is designed to seamlessly integrate into your workflow without altering your existing systems or data structures. Here's how it helps:

- **Non-Intrusive Workflow**: Fastshot works as a desktop application, so you don't need to change your current workflow.
- **Quick Access**: With customizable hotkeys, you can perform most operations swiftly, without interrupting your tasks.
- **Data Integration**: Easily extract and manipulate data from screenshots, enhancing productivity.
- **GenAI Integration**: The GenAI assistant provides intelligent responses and insights, reducing the time spent on manual analysis.

By providing powerful tools for capturing, annotating, and sharing screen content, Fastshot is an indispensable asset for anyone who requires efficient multitasking capabilities in their daily activities.



## Plugin Mechanism

The plugin system in Fastshot is designed to be simple yet powerful, enabling developers to add custom functionalities without modifying the core application code. Plugins are Python modules that adhere to a specific interface, allowing the main application to load, manage, and execute them seamlessly.

###  How the Plugin System Works
- **Plugin Discovery:** On startup, Fastshot scans the plugins directory for plugin modules.
- **Dynamic Loading:** The application dynamically imports each plugin using Python's importlib.
- **Metadata Extraction:** Each plugin provides metadata (e.g., name, ID, description) through a get_plugin_info() function.
- **Hotkey Registration:** Plugins specify default keyboard shortcuts and activation criteria (e.g., pressing the Alt key three times). The main application registers these hotkeys.
- **Execution:** When a plugin's activation criteria are met, the main application calls the plugin's run(app_context) function, passing the application context for interaction.

###  Plugin Structure
A plugin can be a single Python file placed directly in the plugins directory or a package (folder with an __init__.py file) if it requires multiple modules or resources.

####  Plugin Metadata
Each plugin must define a get_plugin_info() function that returns a dictionary with the following keys:
- **name**: Human-readable name of the plugin.
- **id**: Unique identifier for the plugin.
- **description**: Brief description of the plugin's functionality.
- **author**: Author's name.
- **version**: Version of the plugin.
- **default_shortcut**: Default keyboard shortcut to activate the plugin (e.g., 'alt').
- **press_times**: Number of consecutive times the shortcut key must be pressed to activate the plugin.
- **enabled**: Boolean indicating whether the plugin is enabled by default.

####  Plugin Entry Point
Each plugin must implement a run(app_context) function, which is the entry point when the plugin is activated. The app_context parameter provides access to the main application and allows the plugin to interact with it.

###  Developing a Plugin
Follow these steps to create a plugin for Fastshot.

####  Step 1: Create the Plugin File
Navigate to the plugins directory in the Fastshot application.
Create a new Python file for your plugin (e.g., my_plugin.py).

####  Step 2: Define Plugin Metadata
In your plugin file, define the get_plugin_info() function:
```python
def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'My Plugin',
        'id': 'my_plugin',
        'description': 'A plugin that does something useful.',
        'author': 'Your Name',
        'version': '1.0',
        'default_shortcut': 'alt',
        'press_times': 3,
        'enabled': True
    }
```
Note: Adjust the default_shortcut and press_times to suit your plugin's activation method.

####  Step 3: Implement the run Function
Implement the run(app_context) function, which contains the code to be executed when the plugin is activated:

```python
def run(app_context):
    """The main function that gets called when the plugin is activated."""
    # Your plugin code here
    print("My Plugin has been activated!")
```
Example: You might display a message box, manipulate application data, or perform any desired action.
####  Step 4: Use the Application Context (Optional)
If your plugin needs to interact with the main application, use the app_context parameter:

```python
def run(app_context):
    """The main function that gets called when the plugin is activated."""
    # Access application attributes or methods
    app_context.some_method()
```
Note: Refer to the application documentation for available methods and attributes.
####  Step 5: Test the Plugin
Start the Fastshot application.
Activate the plugin by pressing the specified shortcut key the required number of times within one second.
Verify that the plugin behaves as expected.

###  Example Plugin
Below is an example of a simple plugin that displays a "Hello, World!" message when activated.

```python
# plugins/plugin_hello_world.py
import tkinter as tk
from tkinter import messagebox

def get_plugin_info():
    """Returns metadata about the plugin."""
    return {
        'name': 'Hello World Plugin',
        'id': 'plugin_hello_world',
        'description': 'Displays a Hello World message.',
        'author': 'Your Name',
        'version': '1.0',
        'default_shortcut': 'alt',
        'press_times': 3,
        'enabled': True
    }

def run(app_context):
    """The main function that gets called when the plugin is activated."""
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Hello Plugin", "Hello, World!")
    root.destroy()
```
Activation: Press the Alt key three times within one second to activate this plugin.

###  Plugin Configuration
Default Shortcuts: Plugins specify default shortcuts in their metadata.
User Configuration: In future versions, users will be able to modify plugin settings (e.g., shortcuts, enable/disable) through the application's web portal or configuration files.
Conflict Avoidance: Ensure your plugin's shortcut doesn't conflict with existing shortcuts.

###  Best Practices
Unique IDs: Assign a unique id to your plugin to prevent conflicts.
Error Handling: Include try-except blocks in your plugin code to handle exceptions gracefully.
Minimal Impact: Ensure your plugin doesn't negatively impact the application's performance or stability.
Documentation: Comment your code and provide clear explanations of your plugin's functionality.
Security: Avoid executing untrusted code and be cautious with file and network operations.

###  Security Considerations
Trust: Only use plugins from trusted sources to prevent security risks.
Sandboxing: Currently, plugins run with the same permissions as the main application. Be mindful of this when developing plugins.
Validation: Future versions may include security enhancements, such as plugin signing or sandboxing mechanisms.

###  Contributing Plugins
Share Your Plugin: If you've developed a plugin that could benefit others, consider contributing it to the project.
Contribution Guidelines: Follow the project's contribution guidelines for submitting plugins.
Collaboration: Engage with the community to improve and expand plugin functionalities.





## Todo:
1. ~~tk window force trigger~~
2. ~~ppocr[Default]~~
3. ~~screenpen integration~~
4. ~~hyder~~
5. ~~transprent window~~
6. ~~fixed on top~~
7. pyinstaller
8. ~~gdt-4o multimodal task(OCR/QA)~~
9. ~~UI(PySimpleGUI/WebPortal)~~
10. TTS/STT
11. ~~openai-llm-adoption~~
12. ~~Documents~~
13. ~~config-env~~
14. copy&paste image into the Ask Dialog
15. ~~Global Ask Dialog~~AS

17. predefined prompt for ask
18. D-board name
19. OCR Packaging.




20. ~~透明度单向循环。（100-->90-->80-->70-->60-->50-->40-->30-->20-->10 --> 100 --> ......)~~
21. tk window force bring to front again
22. tk window trigger clean previous window.

16. 2nd color for screenpen + Highlighter

