from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Include the optional VAD assets (silero_*.onnx) bundled with faster_whisper.
hiddenimports = collect_submodules("faster_whisper")
datas = collect_data_files("faster_whisper", includes=["assets/*"])
