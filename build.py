# build.py

import os
import shutil
import subprocess
import sys

# --- Конфигурация ---
APP_NAME = "TelethonManager"
MAIN_SCRIPT = "gui_app.py"
ICON_FILE = "icon.ico"
APP_VERSION = "1.6.0"
DIST_FOLDER = f"{APP_NAME}_v{APP_VERSION}"
MANUAL_DLL = "sqlite3.dll"

# --- Содержимое README ---
# Этот текст на русском, но он записывается в файл, а не выводится в консоль, поэтому он безопасен.
README_CONTENT = f"""
# {APP_NAME} v{APP_VERSION}

Профессиональное десктопное приложение для автоматизированного управления и обработки аккаунтов Telegram.

---

## Рабочий процесс

1.  **Первый запуск:** Запустите `{APP_NAME}.exe`. Программа автоматически создаст все нужные файлы и папки.
2.  **Настройка:**
    - Поместите файлы `.session` в папку `sessions`.
    - Отредактируйте `profile_data.csv`, добавив данные для ребрендинга.
    - Используйте кнопки настроек в интерфейсе для конфигурации API, прокси, 2FA-паролей и ссылок.
3.  **Проверка:** Нажмите **"🔎 ПРОВЕРКА"**. Рабочие сессии попадут в `checked_active`.
4.  **Обработка:** Нажмите **"🚀 Обработать активные"**, чтобы взять в работу только проверенные аккаунты.
5.  **Очистка:** Нажмите **"🗑️ Очистить папки"**, чтобы подготовиться к новой партии.
"""

def main():
    print(f"--- Starting build process for {APP_NAME} v{APP_VERSION} ---")

    # 1. Check for PyInstaller
    try:
        import PyInstaller
        print("--> PyInstaller found.")
    except ImportError:
        print("--> PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("--> PyInstaller installed successfully.")

    # 2. Command assembly
    separator = ';' if sys.platform == 'win32' else ':'
    
    command = [
        "pyinstaller", "--noconfirm", "--onefile", "--windowed",
        "--clean", # Force cache clean
        f"--name={APP_NAME}", f"--icon={ICON_FILE}",
        "--hidden-import=customtkinter", "--hidden-import=PIL", "--hidden-import=asyncio",
        f"--add-data=ru.json{separator}.", f"--add-data=en.json{separator}."
    ]
    
    if os.path.exists(MANUAL_DLL):
        print(f"--> Found {MANUAL_DLL}. Adding it to the build.")
        command.append(f"--add-binary={MANUAL_DLL}{separator}.")
    else:
        print(f"--> WARNING: {MANUAL_DLL} not found. The build might be unstable.")
        
    command.append(MAIN_SCRIPT)

    print("\n--> Running PyInstaller...")
    print(f"   Command: {' '.join(command)}")

    # 3. Build execution
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print("\n--- PYINSTALLER BUILD FAILED! ---")
            print("--- STDOUT ---"); print(stdout)
            print("--- STDERR ---"); print(stderr); sys.exit(1)
        else:
            print("--> Build process stdout:")
            print(stdout)
            print("--> Build successful.")
    except Exception as e:
        print(f"\nCRITICAL ERROR during build execution: {e}"); sys.exit(1)

    # 4. Create distribution folder
    print(f"\n--> Creating distribution folder: '{DIST_FOLDER}'")
    if os.path.exists(DIST_FOLDER): shutil.rmtree(DIST_FOLDER)
    os.makedirs(DIST_FOLDER)

    # 5. Move EXE
    exe_path = os.path.join("dist", f"{APP_NAME}.exe")
    if os.path.exists(exe_path):
        shutil.move(exe_path, DIST_FOLDER)
        print(f"   - Moved {APP_NAME}.exe")
    else:
        print(f"--> ERROR: Could not find the built EXE file at {exe_path}!"); sys.exit(1)
        
    # 6. Create README.md
    readme_path = os.path.join(DIST_FOLDER, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(README_CONTENT)
    print("   - Created README.md")

    # 7. Cleanup
    print("\n--> Cleaning up temporary files...")
    for item in ["build", "dist", f"{APP_NAME}.spec"]:
        if os.path.isdir(item): shutil.rmtree(item)
        elif os.path.isfile(item): os.remove(item)
    print("   - Temporary files removed.")
    
    print(f"\n--- BUILD PROCESS FOR v{APP_VERSION} COMPLETED SUCCESSFULLY! ---")
    print(f"--> Your application is ready in the folder: '{DIST_FOLDER}'")

if __name__ == "__main__":
    main()
