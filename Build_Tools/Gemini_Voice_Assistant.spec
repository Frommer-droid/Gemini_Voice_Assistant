# -*- coding: utf-8 -*-
import os
import sys
import certifi

block_cipher = None
spec_path = os.path.abspath(sys.argv[0])
spec_dir = os.path.dirname(spec_path)
project_root = os.path.abspath(os.path.join(spec_dir, '..'))
script_path = os.path.join(project_root, 'gemini_voice_assistant.py')

added_files = [
    (os.path.join(project_root, 'paste_text.exe'), '.'),
    (os.path.join(project_root, 'nircmd.exe'), '.'),
    (os.path.join(project_root, 'xray.exe'), '.'),
]

print("=" * 60)
print("Files to include:")
for src, dst in added_files:
    if os.path.exists(src):
        print(f"  [OK] {os.path.basename(src)}")
    else:
        print(f"  [MISSING] {os.path.basename(src)}")
print("=" * 60)

added_files = [(src, dst) for src, dst in added_files if os.path.exists(src)]

certifi_path = os.path.join(os.path.dirname(certifi.__file__), 'cacert.pem')
if os.path.exists(certifi_path):
    added_files.append((certifi_path, 'certifi'))
    print("[OK] Added certifi certificate\n")

a = Analysis(
    [script_path],
    pathex=[project_root],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'pyaudio', 'sounddevice', 'numpy', 'faster_whisper',
        'ctranslate2', 'tokenizers', 'huggingface_hub',
        'huggingface_hub.hf_api', 'huggingface_hub.constants',
        'huggingface_hub.file_download', 'onnxruntime',
        'onnxruntime.capi._pybind_state', 'google.genai',
        'google.ai.generativelanguage', 'google.auth',
        'certifi', 'ssl', '_ssl', 'urllib3', 'urllib3.util.ssl_',
        'urllib3.contrib.pyopenssl', 'requests', 'requests.adapters',
        'requests.packages.urllib3', 'charset_normalizer',
        'pynput.keyboard', 'pyperclip', 'vless_manager',
        'subprocess', 'socket', 'urllib.parse',
    ],
    hookspath=[spec_dir],
    runtime_hooks=[],
    excludes=[
        'onnxruntime.providers.cuda', 'onnxruntime.providers.tensorrt',
        'onnxruntime.providers.dml', 'matplotlib', 'PIL',
        'tkinter', 'torch', 'tensorflow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

certifi_dir = os.path.dirname(certifi.__file__)
for root, dirs, files in os.walk(certifi_dir):
    for file in files:
        if file.endswith(('.pem', '.txt')):
            file_path = os.path.join(root, file)
            target_path = os.path.join('certifi', os.path.relpath(file_path, certifi_dir))
            a.datas.append((target_path, file_path, 'DATA'))

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Gemini_Voice_Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'logo.ico') if os.path.exists(os.path.join(project_root, 'logo.ico')) else None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name='Gemini_Voice_Assistant',
)
