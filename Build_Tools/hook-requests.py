from PyInstaller.utils.hooks import collect_data_files

# Requests подтягивает сертификаты и шаблоны.
datas = collect_data_files("requests", include_py_files=True)
