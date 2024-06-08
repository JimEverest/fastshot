from setuptools import setup, find_packages

setup(
    name='fastshot',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "pyautogui",
        "pynput",
        "pillow",
        "screeninfo",
        "mss",
        "Pillow",
        "pyperclip",
        "pywin32",
        "paddleocr",
        "paddlepaddle"
    ],
    entry_points={
        'console_scripts': [
            'fastshot = fastshot.main:main',
        ],
    },
    author='Your Name',
    author_email='your-email@example.com',
    description='A versatile screen capturing tool with annotation and OCR features',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/fastshot',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
