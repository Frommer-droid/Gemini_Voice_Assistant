# -*- coding: utf-8 -*-
"""
POST-BUILD CLEANUP SCRIPT
Автоматически копирует файлы и очищает временные папки после компиляции
"""

import os
import shutil

def main():
    print("\n" + "=" * 60)
    print("POST-BUILD CLEANUP")
    print("=" * 60)

    script_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    dist_app_dir = os.path.join(script_dir, 'dist', 'Gemini_Voice_Assistant')
    final_app_dir = os.path.join(project_root, 'Gemini_Voice_Assistant')
    
    # ========== 1. КОПИРУЕМ logo.ico ==========
    logo_source = os.path.join(project_root, 'logo.ico')
    logo_dest = os.path.join(dist_app_dir, 'logo.ico')
    
    if os.path.exists(logo_source) and os.path.exists(dist_app_dir):
        try:
            shutil.copy2(logo_source, logo_dest)
            print(f"[OK] Copied logo.ico")
        except Exception as e:
            print(f"[ERROR] Failed to copy logo.ico: {e}")
    else:
        print(f"[SKIP] logo.ico or dist not found")

    # ========== 1a. Копируем VERSION ==========
    version_source = os.path.join(project_root, 'VERSION')
    version_dest = os.path.join(dist_app_dir, 'VERSION')

    if os.path.exists(version_source) and os.path.exists(dist_app_dir):
        try:
            shutil.copy2(version_source, version_dest)
            print(f"[OK] Copied VERSION")
        except Exception as e:
            print(f"[ERROR] Failed to copy VERSION: {e}")
    else:
        print(f"[SKIP] VERSION or dist not found")
    
    # ========== 2. КОПИРУЕМ whisper_models ==========
    whisper_source = os.path.join(project_root, 'whisper_models')
    whisper_dest = os.path.join(dist_app_dir, 'whisper_models')
    
    if os.path.exists(whisper_source) and os.path.exists(dist_app_dir):
        try:
            if os.path.exists(whisper_dest):
                shutil.rmtree(whisper_dest)
            shutil.copytree(whisper_source, whisper_dest)
            file_count = sum(len(files) for _, _, files in os.walk(whisper_dest))
            print(f"[OK] Copied whisper_models ({file_count} files)")
        except Exception as e:
            print(f"[ERROR] Failed to copy whisper_models: {e}")
    else:
        print(f"[SKIP] whisper_models or dist not found")
    
    # ========== 3. ПЕРЕНОСИМ Gemini_Voice_Assistant ==========
    if os.path.exists(dist_app_dir):
        try:
            if os.path.exists(final_app_dir):
                shutil.rmtree(final_app_dir)
                print(f"[OK] Removed old Gemini_Voice_Assistant/")
            shutil.move(dist_app_dir, final_app_dir)
            print(f"[OK] Moved to: {final_app_dir}")
        except Exception as e:
            print(f"[ERROR] Failed to move: {e}")
    else:
        print("[ERROR] dist/Gemini_Voice_Assistant not found!")

    # ========== 3a. Копируем settings.json ==========
    settings_source = os.path.join(project_root, 'settings.json')
    settings_dest = os.path.join(final_app_dir, 'settings.json')

    if os.path.exists(settings_source) and os.path.exists(final_app_dir):
        try:
            shutil.copy2(settings_source, settings_dest)
            print(f"[OK] Copied settings.json")
        except Exception as e:
            print(f"[ERROR] Failed to copy settings.json: {e}")
    else:
        print("[SKIP] settings.json or final app dir not found")

    # ========== 4. УДАЛЯЕМ ВРЕМЕННЫЕ ПАПКИ ==========
    print("\n[CLEANUP] Removing temporary directories...")
    temp_folders = [
        os.path.join(script_dir, 'build'),
        os.path.join(script_dir, 'dist'),
        os.path.join(script_dir, '__pycache__'),
        os.path.join(project_root, 'dist'),
        os.path.join(project_root, 'build'),
        os.path.join(project_root, '__pycache__'),
        os.path.join(final_app_dir, '__pycache__'),
    ]

    for folder_path in temp_folders:
        if folder_path and os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"[OK] Removed {folder_path}/")
            except Exception as e:
                print(f"[ERROR] Failed to remove {folder_path}/: {e}")
    
    print("\n" + "=" * 60)
    print(f"DONE! App: {final_app_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
