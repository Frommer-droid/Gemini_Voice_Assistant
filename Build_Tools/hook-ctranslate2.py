from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# Подхватываем .dll/.so и данные для ctranslate2
binaries = collect_dynamic_libs("ctranslate2")
datas = collect_data_files("ctranslate2")
