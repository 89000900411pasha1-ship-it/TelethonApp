# gui_app.py

import customtkinter as ctk
import threading
import os
import shutil
import tkinter as tk
import webbrowser
import urllib.request
import json
import configparser
from tkinter import messagebox
from telethon_manager import (
    TelethonProcessor, DataManager, ConfigManager, SESSIONS_DIR, PROCESSED_DIR, 
    FAILED_DIR, CHECKED_ACTIVE_DIR, CHECKED_BANNED_DIR
)

class LanguageManager:
    def __init__(self, language_code='ru'):
        self.language_code = language_code
        self.strings = self.load_language(language_code)

    def load_language(self, lang_code):
        try:
            # Эта строка важна для работы .EXE
            base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
            filepath = os.path.join(base_path, f"{lang_code}.json")
            with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return {}

    def get(self, key, **kwargs):
        template = self.strings.get(key, key)
        try: return template.format(**kwargs)
        except (KeyError, TypeError): return template

class UpdateChecker:
    def __init__(self, config_manager, callback):
        self.config_manager, self.callback = config_manager, callback
        self.current_version = self.config_manager.get_value('Version', 'current_version', '0.0.0')
        self.check_url = self.config_manager.get_value('Version', 'update_check_url')
    def check(self):
        if not self.check_url: return
        try:
            with urllib.request.urlopen(self.check_url, timeout=5) as response: data = response.read().decode('utf-8')
            latest_version = self.parse_version_info(data, 'latest_version')
            if self.is_newer(latest_version, self.current_version):
                message = self.parse_version_info(data, 'message') or f"Доступна новая версия: {latest_version}"
                self.callback(message, latest_version)
        except Exception as e: print(f"Update check failed: {e}")
    @staticmethod
    def parse_version_info(data: str, key: str) -> str:
        for line in data.splitlines():
            if line.startswith(f"{key}="): return line.split('=', 1)[1].strip()
        return ""
    @staticmethod
    def is_newer(latest_v_str, current_v_str):
        latest = tuple(map(int, (latest_v_str or '0').split('.'))); current = tuple(map(int, (current_v_str or '0').split('.')))
        return latest > current

#<editor-fold desc="GUI Widgets and Windows">
class SuperEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.menu = tk.Menu(self, tearoff=0, background="#2B2B2B", foreground="white", activebackground="#565B5E", activeforeground="white", borderwidth=0)
        self.menu.add_command(label="Вырезать", command=self.cut_text); self.menu.add_command(label="Копировать", command=self.copy_text); self.menu.add_command(label="Вставить", command=self.paste_text)
        self.bind("<Button-3>", self.show_menu); self.bind("<Control-x>", self.cut_text); self.bind("<Control-c>", self.copy_text); self.bind("<Control-v>", self.paste_text)
    def show_menu(self, event): self.menu.tk_popup(event.x_root, event.y_root)
    def cut_text(self, event=None): self.copy_text(); self.delete(tk.SEL_FIRST, tk.SEL_LAST); return "break"
    def copy_text(self, event=None): self.clipboard_clear(); self.clipboard_append(self.selection_get()); return "break"
    def paste_text(self, event=None):
        try: self.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError: pass
        self.insert(tk.INSERT, self.clipboard_get()); return "break"

class SuperTextbox(ctk.CTkTextbox):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.menu = tk.Menu(self, tearoff=0, background="#2B2B2B", foreground="white", activebackground="#565B5E", activeforeground="white", borderwidth=0)
        self.menu.add_command(label="Копировать", command=self.copy_text); self.menu.add_separator(); self.menu.add_command(label="Выделить всё", command=self.select_all)
        self.bind("<Button-3>", self.show_menu); self.bind("<Control-c>", self.copy_text); self.bind("<Control-C>", self.copy_text); self.bind("<Control-a>", self.select_all); self.bind("<Control-A>", self.select_all)
        self.bind("<Key>", lambda e: "break")
    def show_menu(self, event): self.menu.tk_popup(event.x_root, event.y_root)
    def copy_text(self, event=None):
        try: self.clipboard_clear(); self.clipboard_append(self.selection_get())
        except tk.TclError: pass
        return "break"
    def select_all(self, event=None): self.tag_add(tk.SEL, "1.0", tk.END); return "break"

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, title_key):
        super().__init__(parent); self.transient(parent); self.grab_set();
        self.parent, self.lang, self.config_manager = parent, parent.lang, parent.config_manager
        self.title(self.lang.get(title_key)); self.resizable(False, False)

class GeneralSettingsWindow(SettingsWindow):
    def __init__(self, parent):
        super().__init__(parent, "general_settings_title")
        ctk.CTkLabel(self, text=self.lang.get("general_settings_language")).pack(padx=15, pady=(15, 5))
        self.lang_var = ctk.StringVar(value=self.config_manager.get_value('General', 'language', 'ru'))
        ctk.CTkOptionMenu(self, variable=self.lang_var, values=['en', 'ru']).pack(padx=15, pady=5)
        ctk.CTkLabel(self, text=self.lang.get("general_settings_theme")).pack(padx=15, pady=(15, 5))
        self.theme_var = ctk.StringVar(value=self.config_manager.get_value('General', 'theme', 'Dark'))
        ctk.CTkOptionMenu(self, variable=self.theme_var, values=['Light', 'Dark', 'System']).pack(padx=15, pady=5)
        ctk.CTkButton(self, text=self.lang.get("save"), command=self.save).pack(padx=15, pady=20)
    def save(self):
        self.config_manager.set_value('General', 'language', self.lang_var.get())
        self.config_manager.set_value('General', 'theme', self.theme_var.get())
        self.parent.apply_theme(); self.parent.log_message(self.lang.get("general_settings_saved")); self.destroy()

class ApiSettingsWindow(SettingsWindow):
    def __init__(self, parent):
        super().__init__(parent, "settings_api_title");
        cfg = self.config_manager.get_section('Telegram')
        ctk.CTkLabel(self, text="API ID:").pack(padx=15, pady=(15, 5))
        self.api_id_entry = SuperEntry(self, width=300); self.api_id_entry.insert(0, cfg.get('api_id', '')); self.api_id_entry.pack(padx=15)
        ctk.CTkLabel(self, text="API Hash:").pack(padx=15, pady=(15, 5))
        self.api_hash_entry = SuperEntry(self, width=300); self.api_hash_entry.insert(0, cfg.get('api_hash', '')); self.api_hash_entry.pack(padx=15)
        ctk.CTkButton(self, text=self.lang.get("save"), command=self.save).pack(padx=15, pady=20)
    def save(self):
        self.config_manager.set_value('Telegram', 'api_id', self.api_id_entry.get()); self.config_manager.set_value('Telegram', 'api_hash', self.api_hash_entry.get())
        self.parent.log_message(self.lang.get("api_settings_saved")); self.destroy()

class LinksSettingsWindow(SettingsWindow):
    def __init__(self, parent):
        super().__init__(parent, "links_settings_title"); self.geometry("600x650")
        links = self.config_manager.get_section('BotLinks')
        scroll_frame = ctk.CTkScrollableFrame(self, label_text=self.lang.get("links_label")); scroll_frame.pack(padx=15, pady=15, fill="both", expand=True)
        self.entries = []
        for i in range(1, 11):
            link_key = f'link{i}'; current_link = links.get(link_key, '')
            row = ctk.CTkFrame(scroll_frame, fg_color="transparent"); row.pack(fill="x", padx=5, pady=8)
            ctk.CTkLabel(row, text=f'{self.lang.get("link_field_prefix")} {i}:', width=80).pack(side="left")
            entry = SuperEntry(row, placeholder_text="https://t.me/..."); entry.insert(0, current_link); entry.pack(side="left", fill="x", expand=True, padx=(10,0))
            self.entries.append(entry)
        ctk.CTkButton(self, text=self.lang.get("save"), command=self.save).pack(padx=15, pady=15, fill="x")
    def save(self):
        for i, entry in enumerate(self.entries): self.config_manager.set_value('BotLinks', f'link{i+1}', entry.get())
        self.parent.log_message(self.lang.get("links_settings_saved")); self.destroy()

class ProxySettingsWindow(SettingsWindow):
    def __init__(self, parent):
        super().__init__(parent, "proxy_settings_title"); self.geometry("500x400")
        enabled = self.config_manager.config.getboolean('Proxy', 'enabled', fallback=False)
        switch_var = ctk.StringVar(value="on" if enabled else "off")
        self.proxy_switch = ctk.CTkSwitch(self, text=self.lang.get("use_proxy"), variable=switch_var, onvalue="on", offvalue="off"); self.proxy_switch.pack(padx=15, pady=15)
        ctk.CTkLabel(self, text=self.lang.get("proxy_list_label")).pack(padx=15, pady=5)
        self.proxy_textbox = ctk.CTkTextbox(self, height=200, font=("Courier New", 12)); self.proxy_textbox.pack(padx=15, pady=5, fill="both", expand=True)
        self.proxy_textbox.insert("1.0", self.config_manager.get_value('Proxy', 'proxies', ''))
        ctk.CTkButton(self, text=self.lang.get("save"), command=self.save).pack(padx=15, pady=15, fill="x")
    def save(self):
        self.config_manager.set_value('Proxy', 'enabled', "yes" if self.proxy_switch.get() == "on" else "no"); self.config_manager.set_value('Proxy', 'proxies', self.proxy_textbox.get("1.0", "end-1c"))
        self.parent.log_message(self.lang.get("proxy_settings_saved")); self.destroy()

class TwoFASettingsWindow(SettingsWindow):
    def __init__(self, parent):
        super().__init__(parent, "twofa_settings_title"); self.geometry("500x400")
        ctk.CTkLabel(self, text=self.lang.get("twofa_list_label")).pack(padx=15, pady=10)
        self.twofa_textbox = ctk.CTkTextbox(self, height=200, font=("Courier New", 12)); self.twofa_textbox.pack(padx=15, pady=5, fill="both", expand=True)
        self.twofa_textbox.insert("1.0", self.config_manager.get_value('TwoFA', 'passwords', ''))
        ctk.CTkButton(self, text=self.lang.get("save"), command=self.save).pack(padx=15, pady=15, fill="x")
    def save(self):
        self.config_manager.set_value('TwoFA', 'passwords', self.twofa_textbox.get("1.0", "end-1c"))
        self.parent.log_message(self.lang.get("twofa_settings_saved")); self.destroy()

class ProcessingSettingsWindow(SettingsWindow):
    def __init__(self, parent):
        super().__init__(parent, "processing_settings_title")
        ctk.CTkLabel(self, text=self.lang.get("retries_on_failure_label")).pack(padx=15, pady=(15, 5))
        self.retries_var = ctk.StringVar(value=self.config_manager.get_value('Processing', 'retries_on_failure', '1'))
        ctk.CTkOptionMenu(self, variable=self.retries_var, values=['0', '1', '2', '3']).pack(padx=15, pady=5)
        ctk.CTkButton(self, text=self.lang.get("save"), command=self.save).pack(padx=15, pady=20)
    def save(self):
        self.config_manager.set_value('Processing', 'retries_on_failure', self.retries_var.get())
        self.parent.log_message(self.lang.get("processing_settings_saved")); self.destroy()
#</editor-fold>

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.processor_thread, self.telethon_processor, self.auto_mode_timer = None, None, None
        self.config_manager = ConfigManager()
        self.lang = LanguageManager(self.config_manager.get_value('General', 'language', 'ru'))
        self.apply_theme()
        self.title(self.lang.get("window_title")); self.geometry("1100x700"); self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(2, weight=1)
        self.setup_ui()
        if DataManager.initialize_environment(self.log_message): self.log_message(self.lang.get("log_env_ready"))
        self.check_readiness()
        self.run_update_check()

    def apply_theme(self): ctk.set_appearance_mode(self.config_manager.get_value('General', 'theme', 'Dark'))
    def setup_ui(self):
        # Top Stats Frame
        prepare_frame = ctk.CTkFrame(self); prepare_frame.grid(row=0, column=0, padx=10, pady=(10,0), sticky="ew")
        prepare_frame.grid_columnconfigure(list(range(6)), weight=1)
        self.sessions_label = ctk.CTkLabel(prepare_frame, text="", font=("Arial", 14)); self.sessions_label.grid(row=0, column=0, pady=5, padx=5)
        self.profiles_label = ctk.CTkLabel(prepare_frame, text="", font=("Arial", 14)); self.profiles_label.grid(row=0, column=1, pady=5, padx=5)
        self.checked_label = ctk.CTkLabel(prepare_frame, text="", font=("Arial", 14)); self.checked_label.grid(row=0, column=2, pady=5, padx=5)
        self.mode_switch = ctk.CTkSwitch(prepare_frame, text=self.lang.get("safe_mode"), command=self.toggle_mode, font=("Arial", 14)); self.mode_switch.grid(row=0, column=3, pady=5); self.mode_switch.select()
        self.auto_mode_switch = ctk.CTkSwitch(prepare_frame, text=self.lang.get("continuous_mode"), font=("Arial", 14)); self.auto_mode_switch.grid(row=0, column=4, pady=5, padx=10)
        self.status_label = ctk.CTkLabel(prepare_frame, text="", text_color="#4CAF50", font=("Arial", 14, "bold")); self.status_label.grid(row=0, column=5, pady=5, padx=5)
        
        # Update Notification Bar
        self.update_label = ctk.CTkLabel(self, text="", text_color="#03A9F4", font=("Arial", 12)); self.update_label.grid(row=1, column=0, sticky="ew", padx=10, pady=0)
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, mode='determinate'); self.progress_bar.set(0); self.progress_bar.grid(row=2, column=0, padx=10, pady=(5,5), sticky="new")
        
        # Log Frame
        log_frame = ctk.CTkFrame(self); log_frame.grid(row=2, column=0, padx=10, pady=(35,5), sticky="nsew")
        self.log_textbox = SuperTextbox(log_frame, font=("Courier New", 12)); self.log_textbox.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Bottom Control Frame
        control_frame = ctk.CTkFrame(self); control_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        control_frame.grid_columnconfigure(0, weight=4); control_frame.grid_columnconfigure(1, weight=2); control_frame.grid_columnconfigure(2, weight=5)
        
        main_actions_frame = ctk.CTkFrame(control_frame, fg_color="transparent"); main_actions_frame.grid(row=0, column=0, sticky="ew")
        self.check_button = ctk.CTkButton(main_actions_frame, text=self.lang.get("check_button"), command=self.start_checking, height=40); self.check_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.start_button = ctk.CTkButton(main_actions_frame, text=self.lang.get("process_button"), command=self.start_processing, height=40); self.start_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.process_active_button = ctk.CTkButton(main_actions_frame, text=self.lang.get("process_active_button"), command=self.start_processing_active, height=40, font=("Arial", 14, "bold")); self.process_active_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.stop_button = ctk.CTkButton(main_actions_frame, text=self.lang.get("stop_button"), command=self.stop_processing, height=40, state="disabled", fg_color="#D32F2F", hover_color="#B71C1C"); self.stop_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        workflow_frame = ctk.CTkFrame(control_frame, fg_color="transparent"); workflow_frame.grid(row=0, column=1, sticky="ew", padx=(10,0))
        self.return_button = ctk.CTkButton(workflow_frame, text=self.lang.get("return_active_button"), command=self.return_active_sessions); self.return_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.clear_button = ctk.CTkButton(workflow_frame, text=self.lang.get("clear_folders_button"), command=self.clear_folders); self.clear_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        settings_frame = ctk.CTkFrame(control_frame, fg_color="transparent"); settings_frame.grid(row=0, column=2, sticky="ew", padx=(10,0))
        self.general_button = ctk.CTkButton(settings_frame, text=self.lang.get("settings_general"), command=lambda: GeneralSettingsWindow(self)); self.general_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.api_button = ctk.CTkButton(settings_frame, text=self.lang.get("settings_api"), command=lambda: ApiSettingsWindow(self)); self.api_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.links_button = ctk.CTkButton(settings_frame, text=self.lang.get("settings_links"), command=lambda: LinksSettingsWindow(self)); self.links_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.proxy_button = ctk.CTkButton(settings_frame, text=self.lang.get("settings_proxy"), command=lambda: ProxySettingsWindow(self)); self.proxy_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.twofa_button = ctk.CTkButton(settings_frame, text=self.lang.get("settings_2fa"), command=lambda: TwoFASettingsWindow(self)); self.twofa_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.processing_button = ctk.CTkButton(settings_frame, text=self.lang.get("settings_processing"), command=lambda: ProcessingSettingsWindow(self)); self.processing_button.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        version = self.config_manager.get_value('Version', 'current_version', '1.6.0')
        self.version_label = ctk.CTkLabel(self, text=f"v{version}", font=("Arial", 10), text_color="gray"); self.version_label.grid(row=4, column=0, sticky="se", padx=10, pady=5)

    def toggle_mode(self): self.mode_switch.configure(text=self.lang.get("safe_mode") if self.mode_switch.get() == 1 else self.lang.get("aggressive_mode"))
    def check_readiness(self):
        try:
            sessions = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]; profiles = DataManager.read_profile_data()
            active_sessions = [f for f in os.listdir(CHECKED_ACTIVE_DIR) if f.endswith('.session')]; banned_sessions = [f for f in os.listdir(CHECKED_BANNED_DIR) if f.endswith('.session')]
            self.sessions_label.configure(text=self.lang.get("sessions_to_process", count=len(sessions))); self.profiles_label.configure(text=self.lang.get("profiles", count=len(profiles))); self.checked_label.configure(text=self.lang.get("active_banned", active=len(active_sessions), banned=len(banned_sessions)))
            ready_for_check, ready_for_process_main, ready_for_process_active = bool(sessions), bool(sessions) and len(profiles) >= len(sessions), bool(active_sessions) and len(profiles) >= len(active_sessions)
            self.check_button.configure(state="normal" if ready_for_check else "disabled"); self.start_button.configure(state="normal" if ready_for_process_main else "disabled")
            self.process_active_button.configure(state="normal" if ready_for_process_active else "disabled"); self.return_button.configure(state="normal" if active_sessions else "disabled")
            if not ready_for_check and not active_sessions: self.status_label.configure(text=self.lang.get("status_waiting"), text_color="#FFA000")
            elif not ready_for_process_main and not ready_for_process_active: self.status_label.configure(text=self.lang.get("status_low_profiles", count=max(len(sessions), len(active_sessions))), text_color="#F44336")
            else: self.status_label.configure(text=self.lang.get("status_ready"), text_color="#4CAF50")
        except Exception as e: self.log_message(f"Ошибка проверки: {e}")

    def log_message(self, message):
        def updater(): self.log_textbox.insert("end", str(message) + "\n"); self.log_textbox.see("end")
        self.after(0, updater)

    def update_progress(self, stats):
        def updater():
            total, current = stats['total'], stats['current']
            self.progress_bar.set(current / total if total > 0 else 0)
            sessions_left = total - current if source_dir == SESSIONS_DIR else len([f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')])
            self.sessions_label.configure(text=self.lang.get("sessions_to_process", count=sessions_left))
            active = len([f for f in os.listdir(CHECKED_ACTIVE_DIR) if f.endswith('.session')]); banned = len([f for f in os.listdir(CHECKED_BANNED_DIR) if f.endswith('.session')])
            self.checked_label.configure(text=self.lang.get("active_banned", active=active, banned=banned))
        self.after(0, updater)
        
    def set_controls_state(self, is_running, mode=""):
        btn_state = "disabled" if is_running else "normal"
        all_buttons = [self.start_button, self.check_button, self.api_button, self.links_button, self.proxy_button, self.twofa_button, self.return_button, self.clear_button, self.process_active_button, self.general_button, self.processing_button]
        for btn in all_buttons: btn.configure(state=btn_state)
        self.mode_switch.configure(state=btn_state); self.auto_mode_switch.configure(state=btn_state)
        self.stop_button.configure(state="normal" if is_running else "disabled")
        if is_running:
            if mode == 'process_main': self.start_button.configure(text="...")
            elif mode == 'process_active': self.process_active_button.configure(text="...")
            elif mode == 'check': self.check_button.configure(text="...")
        else: self.start_button.configure(text=self.lang.get("process_button")); self.check_button.configure(text=self.lang.get("check_button")); self.process_active_button.configure(text=self.lang.get("process_active_button")); self.check_readiness()

    def on_finished(self, mode):
        def updater():
            self.log_message(f"\n{'='*60}\n{self.lang.get('log_finished_cycle', mode=mode.upper())}\n{'='*60}")
            self.set_controls_state(is_running=False)
            self.processor_thread = None
            if self.auto_mode_switch.get() == 1 and mode.startswith('process'):
                self.log_message(self.lang.get('log_continuous_active')); self.status_label.configure(text=self.lang.get("status_searching"), text_color="#03A9F4")
                self.auto_mode_timer = self.after(10000, self.auto_restart_check)
            else: self.log_message(self.lang.get("log_all_work_done")); self.status_label.configure(text=self.lang.get("status_finished"), text_color="#4CAF50")
        self.after(0, updater)

    def auto_restart_check(self):
        self.log_message(self.lang.get("log_restarting_process"))
        if self.check_readiness():
            sessions, profiles = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')], DataManager.read_profile_data()
            if sessions and len(profiles) >= len(sessions):
                self.log_message(self.lang.get("log_new_sessions_found")); self.start_processing()
                return
        self.log_message(self.lang.get("log_no_new_sessions")); self.auto_mode_timer = self.after(10000, self.auto_restart_check)

    def start_processing(self): self._start_task(mode='process', source_dir=SESSIONS_DIR, display_mode='process_main')
    def start_processing_active(self): self._start_task(mode='process', source_dir=CHECKED_ACTIVE_DIR, display_mode='process_active')
    def start_checking(self): self._start_task(mode='check', source_dir=SESSIONS_DIR, display_mode='check')

    def _start_task(self, mode, source_dir, display_mode):
        global source_dir_for_progress
        source_dir_for_progress = source_dir
        if self.auto_mode_timer: self.after_cancel(self.auto_mode_timer); self.auto_mode_timer = None
        self.log_textbox.delete("1.0", "end")
        callbacks = {'log': self.log_message, 'progress': self.update_progress, 'finished': self.on_finished}
        self.telethon_processor = TelethonProcessor(callbacks)
        aggressive_mode = self.mode_switch.get() == 0
        self.set_controls_state(is_running=True, mode=display_mode)
        self.processor_thread = threading.Thread(target=self.telethon_processor.run, args=(aggressive_mode, mode, source_dir), daemon=True)
        self.processor_thread.start()

    def stop_processing(self):
        if self.auto_mode_timer: self.after_cancel(self.auto_mode_timer); self.auto_mode_timer = None
        self.auto_mode_switch.deselect(); self.log_message(self.lang.get("log_stop_signal"))
        if self.telethon_processor: self.telethon_processor.stop()
        self.stop_button.configure(state="disabled", text=self.lang.get("log_stopping"))

    def on_closing(self):
        if self.processor_thread and self.processor_thread.is_alive(): self.stop_processing()
        if self.auto_mode_timer: self.after_cancel(self.auto_mode_timer)
        self.destroy()

    def return_active_sessions(self):
        active_sessions = [f for f in os.listdir(CHECKED_ACTIVE_DIR) if f.endswith('.session')]
        if not active_sessions: self.log_message(self.lang.get("log_return_no_active")); return
        moved_count = 0
        for session_file in active_sessions:
            try: shutil.move(os.path.join(CHECKED_ACTIVE_DIR, session_file), os.path.join(SESSIONS_DIR, session_file)); moved_count += 1
            except Exception as e: self.log_message(self.lang.get("log_return_fail", file=session_file, error=e))
        self.log_message(self.lang.get("log_return_success", count=moved_count)); self.check_readiness()

    def clear_folders(self):
        if not messagebox.askyesno(self.lang.get("log_clear_confirm_title"), self.lang.get("log_clear_confirm_msg")):
            self.log_message(self.lang.get("log_clear_cancel")); return
        folders_to_clear = [PROCESSED_DIR, FAILED_DIR, CHECKED_ACTIVE_DIR, CHECKED_BANNED_DIR]; cleared_count = 0
        for folder in folders_to_clear:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path); cleared_count += 1
                except Exception as e: self.log_message(self.lang.get("log_clear_fail", path=file_path, error=e))
        self.log_message(self.lang.get("log_clear_success", count=cleared_count)); self.check_readiness()

    def run_update_check(self):
        checker = UpdateChecker(self.config_manager, self.show_update_notification)
        threading.Thread(target=checker.check, daemon=True).start()

    def show_update_notification(self, message, version):
        def updater():
            self.update_label.configure(text=self.lang.get("update_available", version=version))
        self.after(0, updater)

if __name__ == "__main__":
    app = App()
    app.mainloop()
