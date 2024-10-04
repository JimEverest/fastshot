from setuptools import setup, find_packages

setup(
    name='fastshot',
    version='1.1.1',
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
        "paddlepaddle",
        "customtkinter"
    ],
    package_data={
        'fastshot': ['config.ini'],  # 明确指示包含 config.ini
    },
    entry_points={
        'console_scripts': [
            'fastshot = fastshot.main:main',
        ],
    },
    author='Jim T',
    author_email='tianwai263@gmail.com',
    description='A versatile screen capturing tool with annotation and OCR features',
    long_description=open('README.md', encoding='utf-8').read(),  # 使用 UTF-8 编码
    long_description_content_type='text/markdown',
    url='https://github.com/jimeverest/fastshot',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
