from setuptools import setup, find_packages
import os

# Read version from __version__.py
def get_version():
    version_file = os.path.join(os.path.dirname(__file__), 'fastshot', '__version__.py')
    version_dict = {}
    with open(version_file, 'r', encoding='utf-8') as f:
        exec(f.read(), version_dict)
    print("setting up ", version_dict['__version__'])
    return version_dict['__version__']

setup(
    name='fastshot',
    version=get_version(),
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        # Cross-platform
        "pynput",
        "pillow",
        "mss",
        "pyperclip",
        "rapidocr>=3.0.0",
        "onnxruntime",
        "customtkinter",
        "configparser",
        "openai",
        "httpx>=0.24.0",
        "requests",
        "numpy",
        "boto3>=1.26.0",
        # Windows only
        "pywin32; sys_platform == 'win32'",
        "pyautogui; sys_platform == 'win32'",
        "screeninfo; sys_platform == 'win32'",
        # macOS only
        "pyobjc>=10.0; sys_platform == 'darwin'",
    ],
    package_data={
        'fastshot': [
            'config.ini',
            '_config_reset.ini',
            'plugins/*',
            'plugins/utils/*',
            'resources/*.onnx',
            'app_platform/*',
            'web/templates/*.html',
            'web/static/css/*.css',
            'web/static/js/*.js',
            'web/static/images/*.png',
        ],
    },
    entry_points={
        'console_scripts': [
            'fastshot = fastshot.main:main',
        ],
    },
    author='Jim T',
    author_email='tianwai263@gmail.com',
    description='A versatile screen capturing tool with annotation and OCR features',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/jimeverest/fastshot',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
    ],
    python_requires='>=3.9',
)
