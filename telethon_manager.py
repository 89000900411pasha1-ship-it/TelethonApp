# teleton_manager.py

import os
import sys
import configparser
import csv
import shutil
import asyncio
import threading
import random
import re
import logging
from typing import Dict, Any, List

# --- ВАЖНО: Определение путей для корректной работы .EXE ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

#<editor-fold desc="Global Paths">
SESSIONS_DIR = os.path.join(application_path, 'sessions')
PROCESSED_DIR = os.path.join(application_path, 'processed')
FAILED_DIR = os.path.join(application_path, 'failed')
CHECKED_ACTIVE_DIR = os.path.join(application_path, 'checked_active')
CHECKED_BANNED_DIR = os.path.join(application_path, 'checked_banned')
CONFIG_FILE = os.path.join(application_path, 'config.ini')
PROFILE_DATA_FILE = os.path.join(application_path, 'profile_data.csv')
LOG_FILE = os.path.join(application_path, 'app.log')
#</editor-fold>

# --- Настройка логирования в файл ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=LOG_FILE, filemode='a', encoding='utf-8')

# --- Импорты, необходимые для Telethon ---
from telethon.sync import TelegramClient
from telethon.tl.functions.photos import DeletePhotosRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest, SetPrivacyRequest
from telethon.tl.functions.stories import ReadStoriesRequest
from telethon.tl.types import InputPrivacyKeyStatusTimestamp, InputPrivacyKeyChatInvite, InputPrivacyKeyPhoneCall, InputPrivacyKeyProfilePhoto, InputPrivacyKeyForwards, InputPrivacyKeyPhoneNumber, InputPrivacyValueAllowAll, InputPrivacyValueDisallowAll
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.messages import DeleteHistoryRequest
# ИСПРАВЛЕНИЕ: Удалена ошибка "UsernameTakenError" из импорта для совместимости
from telethon.errors.rpcerrorlist import UsernameNotOccupiedError, UsernameInvalidError, FloodWaitError, UserDeactivatedBanError, UserDeactivatedError, AuthKeyUnregisteredError, SessionPasswordNeededError

#<editor-fold desc="Helpers and Scenarios">
class TelethonHelpers:
    @staticmethod
    async def helper_delete_photos(client, logger):
        try: logger("  - Удаляем все фото профиля..."); await client(DeletePhotosRequest(await client.get_profile_photos('me'))); return True
        except Exception as e: logger(f"  - Ошибка при удалении фото: {e}"); logging.error(f"Failed to delete photos: {e}"); return False
    @staticmethod
    async def helper_clear_bio(client, logger):
        try: logger("  - Очищаем биографию (о себе)..."); await client(UpdateProfileRequest(about='')); return True
        except Exception as e: logger(f"  - Ошибка при очистке био: {e}"); logging.error(f"Failed to clear bio: {e}"); return False
    @staticmethod
    async def helper_clear_name(client, logger):
        try: logger("  - Очищаем имя и фамилию..."); await client(UpdateProfileRequest(first_name='-', last_name='')); return True
        except Exception as e: logger(f"  - Ошибка при очистке имени: {e}"); logging.error(f"Failed to clear name: {e}"); return False
    @staticmethod
    async def helper_clear_username(client, logger):
        try: logger("  - Удаляем юзернейм..."); await client(UpdateUsernameRequest(username='')); return True
        except UsernameNotOccupiedError: logger("  - Юзернейм и так не установлен."); return True
        except Exception as e: logger(f"  - Ошибка при удалении юзернейма: {e}"); logging.error(f"Failed to clear username: {e}"); return False
    @staticmethod
    async def helper_delete_stories(client, logger):
        logger("  - Удаляем все истории...")
        try:
            if hasattr(client, 'get_stories'):
                stories = await client.get_stories('me')
                if stories and stories.stories: await client(ReadStoriesRequest(stories.id, stories.stories[-1].id))
            else: logger("  - Пропускаем: версия Telethon не поддерживает работу с историями.")
            return True
        except Exception as e: logger(f"  - Ошибка при удалении историй: {e}"); logging.error(f"Failed to delete stories: {e}"); return False
    @staticmethod
    async def helper_set_privacy(client, logger):
        logger("  - Устанавливаем настройки конфиденциальности...")
        try:
            rules_to_set_nobody = [(InputPrivacyKeyStatusTimestamp(), "Время последнего захода"), (InputPrivacyKeyChatInvite(), "Приглашения в группы"), (InputPrivacyKeyPhoneCall(), "Звонки"), (InputPrivacyKeyForwards(), "Пересылка сообщений"), (InputPrivacyKeyPhoneNumber(), "Видимость номера телефона")]
            for key, desc in rules_to_set_nobody: logger(f"    - {desc}: Никто"); await client(SetPrivacyRequest(key=key, rules=[InputPrivacyValueDisallowAll()])); await asyncio.sleep(1)
            logger("    - Фото профиля: Все"); await client(SetPrivacyRequest(key=InputPrivacyKeyProfilePhoto(), rules=[InputPrivacyValueAllowAll()]))
            return True
        except Exception as e: logger(f"  - Ошибка при установке приватности: {e}"); logging.error(f"Failed to set privacy: {e}"); return False
    @staticmethod
    async def helper_leave_dialogs(client, aggressive, logger):
        logger("  - Покидаем чаты и каналы...")
        try:
            async for dialog in client.iter_dialogs():
                if dialog.is_channel or dialog.is_group: logger(f"    - Покидаем: {dialog.title}"); await client(LeaveChannelRequest(dialog.id)); await asyncio.sleep(1.5)
            return True
        except Exception as e: logger(f"  - Ошибка при выходе из диалогов: {e}"); logging.error(f"Failed to leave dialogs: {e}"); return False
    @staticmethod
    async def helper_delete_chats(client, aggressive, logger):
        logger("  - Удаляем диалоги...")
        try:
            async for dialog in client.iter_dialogs():
                if not aggressive and dialog.is_user: continue
                try: logger(f"    - Очистка и удаление: {dialog.title}"); await client(DeleteHistoryRequest(peer=await dialog.get_input_entity(), max_id=0, revoke=True)); await asyncio.sleep(1.5)
                except FloodWaitError as fwe: logger(f"    - Flood Wait: ждем {fwe.seconds} секунд..."); logging.warning(f"Flood wait for {fwe.seconds}s"); await asyncio.sleep(fwe.seconds)
                except Exception as e_inner: logger(f"    - Не удалось удалить '{dialog.title}': {e_inner}")
            return True
        except Exception as e: logger(f"  - Глобальная ошибка при удалении диалогов: {e}"); logging.error(f"Global error deleting chats: {e}"); return False
    
    # ИСПРАВЛЕНИЕ: Блок try/except изменен для совместимости
    @staticmethod
    async def helper_update_profile(client, profile_data, logger):
        try:
            first, last, user = profile_data.get('first_name', ''), profile_data.get('last_name', ''), profile_data.get('username', '')
            logger(f"  - Устанавливаем данные: Имя='{first}', Фамилия='{last}', Юзернейм='{user}'")
            if first or last: await client(UpdateProfileRequest(first_name=first, last_name=last))
            if user:
                try:
                    await client(UpdateUsernameRequest(username=user))
                except (UsernameInvalidError, UsernameNotOccupiedError) as e:
                    logger(f"  - Не удалось установить юзернейм '{user}': {e}")
                except Exception as e:
                    if 'USERNAME_OCCUPIED' in str(e):
                         logger(f"  - ПРЕДУПРЕЖДЕНИЕ: Юзернейм '{user}' уже занят. Пропускаем.")
                    else:
                         logger(f"  - Неизвестная ошибка при установке юзернейма '{user}': {e}")
            return True
        except Exception as e: logger(f"  - Ошибка обновления профиля: {e}"); logging.error(f"Failed to update profile: {e}"); return False

    @staticmethod
    async def helper_human_like_bot_activation(client, config, logger):
        logger("\n  [ЭТАП 3/3]: Активация ботов (человечная имитация)...")
        try:
            bot_links = config.get('BotLinks', {}).values(); active_links = [link for link in bot_links if link and link.strip()]
            if not active_links: logger("  - Ссылки на ботов не найдены в config.ini. Пропускаем этап."); return True
            for link in active_links:
                try:
                    logger(f"  - Обрабатываем ссылку: {link}"); await client.send_message('me', link); await asyncio.sleep(random.uniform(2, 4))
                    bot_entity = await client.get_entity(link)
                    if not hasattr(bot_entity, 'username') or not bot_entity.username: logger(f"    - ПРЕДУПРЕЖДЕНИЕ: Не удалось определить юзернейм для {link}. Пропускаем."); continue
                    logger(f"    - Успешно распознан бот @{bot_entity.username}"); await asyncio.sleep(random.uniform(1, 3))
                    await client.send_message(bot_entity, '/start'); await asyncio.sleep(random.uniform(3, 5))
                except ValueError: logger(f"  - ОШИБКА: Некорректная ссылка или юзернейм не найден: {link}")
                except Exception as e_inner: logger(f"  - ОШИБКА при обработке ссылки {link}: {e_inner}")
            logger("  ✅ Активация ботов завершена."); return True
        except Exception as e: logger(f"  - Глобальная ошибка при активации ботов: {e}"); logging.error(f"Global error activating bots: {e}"); return False

class Scenarios:
    @staticmethod
    async def scenario_full_package(client, profile_data, config, aggressive, logger):
        mode_text = "🔥 АГРЕССИВНОМ" if aggressive else "🛡️ БЕЗОПАСНОМ"
        logger(f"  ▶️ Сценарий: ПОЛНЫЙ КОМПЛЕКТ в {mode_text} режиме..."); logger("  [ЭТАП 1/3]: Полная очистка...")
        await TelethonHelpers.helper_delete_photos(client, logger); await asyncio.sleep(1)
        await TelethonHelpers.helper_clear_bio(client, logger); await asyncio.sleep(1)
        await TelethonHelpers.helper_clear_name(client, logger); await asyncio.sleep(1)
        await TelethonHelpers.helper_clear_username(client, logger); await asyncio.sleep(1)
        await TelethonHelpers.helper_delete_stories(client, logger); await asyncio.sleep(1)
        await TelethonHelpers.helper_set_privacy(client, logger); await asyncio.sleep(1)
        await TelethonHelpers.helper_leave_dialogs(client, aggressive, logger)
        await TelethonHelpers.helper_delete_chats(client, aggressive, logger)
        logger("  ✅ Очистка завершена.")
        logger("\n  [ЭТАП 2/3]: Ребрендинг профиля...")
        rebrand_ok = await TelethonHelpers.helper_update_profile(client, profile_data, logger)
        logger("  ✅ Ребрендинг завершен.")
        bots_ok = await TelethonHelpers.helper_human_like_bot_activation(client, config, logger)
        return rebrand_ok and bots_ok
    @staticmethod
    async def scenario_check_account(client, logger):
        logger("  ▶️ Сценарий: ПРОВЕРКА АККАУНТА...")
        try:
            me = await client.get_me()
            if me: logger(f"  - Статус: ✅ Активен. ID: {me.id}, Имя: {me.first_name or ''} (@{me.username or 'N/A'})"); return "ACTIVE"
            raise Exception("Не удалось получить информацию об аккаунте.")
        except (UserDeactivatedBanError, UserDeactivatedError, AuthKeyUnregisteredError) as e:
            logger(f"  - Статус: ❌ ЗАБЛОКИРОВАН или удален. Ошибка: {type(e).__name__}"); return "BANNED"
        except Exception as e: logger(f"  - Статус: ❓ НЕИЗВЕСТНАЯ ОШИБКА. {e}"); return "FAILED"
#</editor-fold>

class ConfigManager:
    DEFAULT_CONFIG = {
        'General': {'language': 'ru', 'theme': 'Dark'},
        'Processing': {'retries_on_failure': '1'},
        'Version': {'current_version': '1.6.0', 'update_check_url': 'https://gist.githubusercontent.com/anthony1708/f92c647b19685a44810758a0327f295b/raw/tm_version.txt'},
        'Telegram': {'api_id': '2040', 'api_hash': 'b18441a1ff607e10a989891a5462e627'},
        'BotLinks': {f'link{i}': '' for i in range(1, 11)},
        'Proxy': {'enabled': 'no', 'proxies': '# socks5:127.0.0.1:1080\n'},
        'TwoFA': {'passwords': '# 12345\n'}
    }
    def __init__(self, filepath=CONFIG_FILE):
        self.filepath = filepath; self.config = configparser.ConfigParser(); self.read()
    def read(self):
        if not os.path.exists(self.filepath): self.create_default_config()
        self.config.read(self.filepath, encoding='utf-8')
    def save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f: self.config.write(f)
    def create_default_config(self):
        for section, options in self.DEFAULT_CONFIG.items(): self.config[section] = options
        self.save()
    def get_value(self, section, key, fallback=None):
        if fallback is None: fallback = self.DEFAULT_CONFIG.get(section, {}).get(key)
        return self.config.get(section, key, fallback=fallback)
    def get_section(self, section) -> Dict:
        return dict(self.config.items(section)) if self.config.has_section(section) else self.DEFAULT_CONFIG.get(section, {})
    def set_value(self, section, key, value):
        if not self.config.has_section(section): self.config.add_section(section)
        self.config.set(section, key, str(value)); self.save()
    @staticmethod
    def _parse_proxy(proxy_str):
        match = re.match(r'(?:(socks5|socks4|http)://)?(?:(.+):(.+)@)?(.+):(\d+)', proxy_str.strip())
        if not match: return None
        proto, user, pwd, host, port = match.groups(); return {"proxy_type": proto or 'socks5', "addr": host, "port": int(port), "username": user, "password": pwd}

class DataManager:
    @staticmethod
    def initialize_environment(logger):
        try:
            folders = [SESSIONS_DIR, PROCESSED_DIR, FAILED_DIR, CHECKED_ACTIVE_DIR, CHECKED_BANNED_DIR]
            for folder in folders: os.makedirs(folder, exist_ok=True)
            if not os.path.exists(CONFIG_FILE):
                logger("--- Обнаружен первый запуск. Создаем окружение... ---"); logging.info("First run detected. Creating environment.")
                ConfigManager().create_default_config(); logger(f"Создан файл конфигурации: {CONFIG_FILE}")
            if not os.path.exists(PROFILE_DATA_FILE):
                with open(PROFILE_DATA_FILE, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f); writer.writerow(['first_name', 'last_name', 'username'])
                    writer.writerows([['Иван', '', 'ivanidzeone'], ['Петр', 'Петров', 'petrov_unique_name']])
                logger(f"Создан файл с примерами профилей: {PROFILE_DATA_FILE}")
            return True
        except Exception as e: logger(f"Критическая ошибка инициализации: {e}"); logging.critical(f"Initialization critical error: {e}", exc_info=True); return False
    @staticmethod
    def read_profile_data():
        if not os.path.exists(PROFILE_DATA_FILE): return []
        try:
            with open(PROFILE_DATA_FILE, 'r', encoding='utf-8') as f: return list(csv.DictReader(f))
        except Exception as e: logging.error(f"Failed to read profile data: {e}"); return []
    @staticmethod
    def write_profile_data(data):
        try:
            with open(PROFILE_DATA_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['first_name', 'last_name', 'username']); writer.writeheader()
                if data: writer.writerows(data)
        except Exception as e: logging.error(f"Failed to write profile data: {e}")

class SessionHandler:
    def __init__(self, session_file: str, source_dir: str, config: Dict[str, Any], ui_logger):
        self.session_file, self.config, self.ui_logger = session_file, config, ui_logger
        self.session_path = os.path.join(source_dir, self.session_file)
        self.client = TelegramClient(self.session_path, self.config['api_id'], self.config['api_hash'], proxy=self.config['proxy'])

    def _log(self, message: str):
        self.ui_logger(message)
        logging.info(f"[{self.session_file}] {message.strip()}")

    async def _connect_with_2fa(self) -> bool:
        try: await self.client.connect()
        except SessionPasswordNeededError:
            self._log(f"  - Требуется пароль 2FA для {self.session_file}. Пытаемся подобрать...")
            for pwd in self.config['twofa_passwords']:
                try: await self.client.sign_in(password=pwd); self._log(f"    - Пароль '{pwd[:2]}...' подошел!"); return True
                except Exception: continue
            self._log("    - Ни один пароль 2FA из списка не подошел."); return False
        return True

    async def execute(self) -> str:
        max_retries = self.config.get('retries', 1)
        for attempt in range(max_retries + 1):
            result_status = "FAILED"
            try:
                if attempt > 0: self._log(f"  - Повторная попытка ({attempt}/{max_retries})...")
                self._log("\n" + "-"*50 + f"\nОбработка: {self.session_file} | Режим: {self.config['mode'].upper()}")
                if self.config['proxy']: self._log(f"  - Используем прокси: {self.config['proxy']['addr']}:{self.config['proxy']['port']}")
                
                if not await self._connect_with_2fa(): raise Exception("Ошибка 2FA.")
                if not await self.client.is_user_authorized(): raise ConnectionError("Сессия не авторизована.")
                
                if self.config['mode'] == 'process':
                    if await Scenarios.scenario_full_package(self.client, self.config['profile_data'], self.config['full_config'], self.config['aggressive'], self._log): result_status = "PROCESSED"
                elif self.config['mode'] == 'check':
                    result_status = await Scenarios.scenario_check_account(self.client, self._log)
                
                break
            
            except (UserDeactivatedBanError, UserDeactivatedError, AuthKeyUnregisteredError, SessionPasswordNeededError):
                self._log(f"  ❌ НЕИСПРАВИМАЯ ОШИБКА в {self.session_file}. Повторная попытка невозможна."); result_status = "BANNED"
                break
            except (asyncio.TimeoutError, ConnectionError) as e:
                self._log(f"  ⚠️ ВРЕМЕННАЯ ОШИБКА в {self.session_file}: {type(e).__name__}."); result_status = "FAILED"
                if attempt < max_retries: await asyncio.sleep(5)
                else: self._log(f"  - Достигнут лимит повторных попыток.")
            except Exception as e:
                self._log(f"  ❌ КРИТИЧЕСКАЯ ОШИБКА в {self.session_file}: {e}"); result_status = "FAILED"
                logging.error(f"Critical error on {self.session_file}: {e}", exc_info=True)
                break
            finally:
                if self.client.is_connected(): await self.client.disconnect()
        
        self._move_session_file(result_status); return result_status

    def _move_session_file(self, status: str):
        dest_map = {'PROCESSED': PROCESSED_DIR, 'ACTIVE': CHECKED_ACTIVE_DIR, 'BANNED': CHECKED_BANNED_DIR, 'FAILED': FAILED_DIR}
        dest_folder = dest_map.get(status, FAILED_DIR)
        try:
            shutil.move(self.session_path, os.path.join(dest_folder, self.session_file))
            self._log(f"  - Результат: {status}. Файл перемещен в '{os.path.basename(dest_folder)}'")
            logging.info(f"Moved {self.session_file} to {os.path.basename(dest_folder)} with status {status}")
        except Exception as e: self._log(f"  - CRITICAL: Не удалось переместить файл сессии! {e}"); logging.error(f"Failed to move {self.session_file}: {e}")

class TelethonProcessor:
    def __init__(self, callbacks):
        self.callbacks, self.stop_event = callbacks, threading.Event()
        self.config_manager = ConfigManager()

    def _log(self, message): self.callbacks['log'](message)
    def _update_progress(self, stats): self.callbacks['progress'](stats)

    async def _main_loop(self, aggressive_mode, mode, source_dir):
        self._log("Загрузка конфигурации..."); logging.info("Starting new task: mode=%s, aggressive=%s", mode, aggressive_mode)
        self.config_manager.read()
        
        telegram_config = self.config_manager.get_section('Telegram')
        proxy_config_raw = self.config_manager.get_section('Proxy')
        proxy_config = {
            'enabled': configparser.ConfigParser.BOOLEAN_STATES.get(proxy_config_raw.get('enabled', 'no').lower()),
            'proxies': [ConfigManager._parse_proxy(p) for p in proxy_config_raw.get('proxies', '').splitlines() if p.strip() and not p.strip().startswith('#')]
        }
        twofa_passwords = [p.strip() for p in self.config_manager.get_section('TwoFA').get('passwords', '').splitlines() if p.strip() and not p.strip().startswith('#')]
        processing_config = self.config_manager.get_section('Processing')
        retries = int(processing_config.get('retries_on_failure', '1'))

        if proxy_config['enabled']:
            if proxy_config['proxies']: self._log(f"✅ Загружено {len(proxy_config['proxies'])} прокси.")
            else: self._log("⚠️ Прокси включены, но список пуст или некорректен!")
        if twofa_passwords: self._log(f"✅ Загружено {len(twofa_passwords)} паролей 2FA.")

        session_files, profile_data_rows = [f for f in os.listdir(source_dir) if f.endswith('.session')], DataManager.read_profile_data()
        stats = {'total': len(session_files), 'current': 0, 'processed': 0, 'failed': 0, 'active': 0, 'banned': 0}
        self._update_progress(stats)

        for i, session_file in enumerate(session_files):
            if self.stop_event.is_set(): self._log("\n❗️ Процесс остановлен пользователем."); logging.info("Task stopped by user."); break
            
            if mode == 'process' and len(profile_data_rows) < (stats['total'] - i):
                self._log(f"Данные для профилей закончились. Требуется {stats['total'] - i}, доступно {len(profile_data_rows)}. Прерываем...");
                logging.warning("Ran out of profile data."); break

            handler_config = {
                "api_id": int(telegram_config.get('api_id', 2040)), "api_hash": telegram_config.get('api_hash', 'b18441a1ff607e10a989891a5462e627'),
                "mode": mode, "aggressive": aggressive_mode,
                "proxy": random.choice(proxy_config['proxies']) if proxy_config['enabled'] and proxy_config['proxies'] else None,
                "twofa_passwords": twofa_passwords,
                "retries": retries,
                "profile_data": profile_data_rows[stats['processed']] if mode == 'process' else {},
                "full_config": self.config_manager.config
            }
            handler = SessionHandler(session_file, source_dir, handler_config, self._log)
            result = await handler.execute()
            
            stats['current'] += 1
            if result == 'PROCESSED': stats['processed'] += 1
            elif result == 'ACTIVE': stats['active'] += 1
            elif result == 'BANNED': stats['banned'] += 1
            else: stats['failed'] += 1
            self._update_progress(stats)

        if stats['processed'] > 0: DataManager.write_profile_data(profile_data_rows[stats['processed']:]); self._log(f"\nℹ️ Данные в {os.path.basename(PROFILE_DATA_FILE)} обновлены.")
        self.callbacks['finished'](mode); logging.info("Task finished. Stats: %s", stats)

    def run(self, aggressive_mode, mode, source_dir):
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try: loop.run_until_complete(self._main_loop(aggressive_mode, mode, source_dir))
        finally: loop.close()

    def stop(self): self.stop_event.set()