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
# ... (здесь находится полный текст README из предыдущих сообщений, он не меняется)
README_CONTENT = f"""
# {APP_NAME} v{APP_VERSION}
... (полный текст инструкции) ...
"""

def main():
    print(f"--- Начало сборки пакета {APP_NAME} v{APP_VERSION} ---")

    # 1. Проверка PyInstaller
    try:
        import PyInstaller
        print("✅ PyInstaller найден.")
    except ImportError:
        print("⚠️ PyInstaller не найден. Устанавливаем...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller успешно установлен.")

    # --- Формирование команды с принудительной очисткой кэша ---
    separator = ';' if sys.platform == 'win32' else ':'
    
    command = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--clean",  # <-- ЭТА КОМАНДА ПРИНУДИТЕЛЬНО ОЧИЩАЕТ КЭШ PYINSTALLER
        f"--name={APP_NAME}",
        f"--icon={ICON_FILE}",
        "--hidden-import=customtkinter",
        "--hidden-import=PIL",
        "--hidden-import=asyncio",
        f"--add-data=ru.json{separator}.",
        f"--add-data=en.json{separator}."
    ]
    
    if os.path.exists(MANUAL_DLL):
        print(f"✅ Найден файл {MANUAL_DLL}. Добавляем его в сборку.")
        command.append(f"--add-binary={MANUAL_DLL}{separator}.")
    else:
        print(f"⚠️ ВНИМАНИЕ: Файл {MANUAL_DLL} не найден. Сборка может быть нестабильной.")
        
    command.append(MAIN_SCRIPT)

    print("\n▶️ Запускаем PyInstaller...")
    print(f"   Команда: {' '.join(command)}")

    # 3. Выполнение сборки
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print("\n❌ ОШИБКА СБОРКИ PYINSTALLER!"); print("--- STDOUT ---"); print(stdout); print("--- STDERR ---"); print(stderr); sys.exit(1)
        else:
            print(stdout) # Выводим лог, даже если успешно
            print("✅ Сборка .EXE успешно завершена.")
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА при запуске сборки: {e}"); sys.exit(1)

    # ... (Остальная часть скрипта (шаги 4, 5, 6, 7) остается без изменений) ...

    # 4. Создание папки для распространения
    print(f"\n📦 Создаем папку: '{DIST_FOLDER}'")
    if os.path.exists(DIST_FOLDER): shutil.rmtree(DIST_FOLDER)
    os.makedirs(DIST_FOLDER)

    # 5. Копирование .EXE
    exe_path = os.path.join("dist", f"{APP_NAME}.exe")
    if os.path.exists(exe_path):
        shutil.move(exe_path, DIST_FOLDER)
        print(f"   - {APP_NAME}.exe перемещен.")
    else:
        print(f"❌ Не удалось найти собранный файл {exe_path}!"); sys.exit(1)
        
    # 6. Создание README.md
    readme_path = os.path.join(DIST_FOLDER, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"# {APP_NAME} v{APP_VERSION}\n\nИнструкция по использованию...") # Краткая версия для примера
    print("   - README.md создан.")

    # 7. Очистка
    print("\n🗑️  Очищаем временные файлы...")
    for item in ["build", "dist", f"{APP_NAME}.spec"]:
        if os.path.isdir(item): shutil.rmtree(item)
        elif os.path.isfile(item): os.remove(item)
    print("   - Временные файлы удалены.")
    
    print(f"\n🎉🎉🎉 ПРОЦЕСС СБОРКИ v{APP_VERSION} ЗАВЕРШЕН! 🎉🎉🎉")
    print(f"Ваше приложение готово в папке: '{DIST_FOLDER}'")

if __name__ == "__main__":
    main()