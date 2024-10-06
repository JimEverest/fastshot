# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_all

datas = [
    ('D:\\AI\\fastshot_build_2\\fastshot\\web\\templates', 'fastshot/web/templates'), 
    ('D:\\AI\\fastshot_build_2\\fastshot\\web\\static', 'fastshot/web/static'), 
    ('D:\\AI\\fastshot_build_2\\fastshot\\resources', 'fastshot/resources'), 
    ('D:\\AI\\fastshot_build_2\\fastshot\\config.ini', 'fastshot'), 
    ('D:\\AI\\fastshot_build_2\\fastshot\\_config_reset.ini', 'fastshot')]
    
binaries = []
hiddenimports = ['PIL._imaging', 'imghdr', 'imgaug', 'pyclipper']
datas += collect_data_files('paddle')
datas += collect_data_files('scipy')
tmp_ret = collect_all('paddleocr')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('lmbd')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('skimage')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('scipy.io')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


block_cipher = None


a = Analysis(
    ['run.py'],
    pathex=['C:\\ProgramData\\anaconda3\\Lib\\site-packages\\paddle\\libs', 'C:\\ProgramData\\anaconda3\\Lib\\site-packages\\paddleocr'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='run',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Administrator\\Downloads\\fastshot.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='run',
)
