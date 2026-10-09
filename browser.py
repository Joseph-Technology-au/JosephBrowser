import sys
import traceback
import platform

# ==========================================
# FATAL ERROR HANDLER (Prevents Instant Close)
# ==========================================
def show_fatal_error(title, msg):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, msg)
    except Exception:
        pass
    print(f"\n{'='*60}\n{title}\n{'='*60}\n{msg}\n")
    input("Press Enter to exit...")
    sys.exit(1)

def exception_hook(exc_type, exc_value, exc_traceback):
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"\nJOSEPH BROWSER CRASHED\n{tb_str}")
    show_fatal_error("Joseph Browser Crashed", f"An unexpected error occurred:\n\n{tb_str}")

sys.excepthook = exception_hook

try:
    import os
    import json
    import requests
    import re
    import time
    import socket
    import subprocess
    import random
    import html as html_lib
    from pathlib import Path
    from urllib.parse import unquote, urlparse
    
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabBar, QVBoxLayout, QHBoxLayout,
                                 QPushButton, QLineEdit, QWidget, QStackedWidget, QTextEdit,
                                 QLabel, QMessageBox, QMenu, QFrame, QSplitter, QComboBox, QFileDialog, QDialog,
                                 QTabWidget, QGridLayout, QProgressBar, QSystemTrayIcon, QSizeGrip, QInputDialog)
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript, QWebEngineUrlRequestInterceptor
    from PyQt6.QtCore import QUrl, Qt, QSize, pyqtSignal, QPoint, QThread, QTimer, QObject, pyqtSlot
    from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QColor, QAction, QPainter, QPen, QPixmap
    from PyQt6.QtNetwork import QNetworkProxy
except Exception as e:
    show_fatal_error("Missing Dependencies", f"Joseph Browser failed to start.\n\n{traceback.format_exc()}\n\nPlease ensure you have run: pip install PyQt6 PyQt6-WebEngine requests")

# ==========================================
# 1. SETTINGS & CONFIGURATION
# ==========================================
BROWSER_VERSION = "2026.10.08"
SCRIPT_DIR = Path(os.path.abspath(__file__)).parent

class SettingsManager:
    def __init__(self):
        self.dir = os.path.join(os.path.expanduser("~"), ".joseph_browser")
        os.makedirs(self.dir, exist_ok=True)
        self.file = os.path.join(self.dir, "settings.json")
        self.defaults = {
            "theme": "system", "accent": "#1c4b82", "wallpaper": "", "extensions": [],
            "search_engine": "duckduckgo", "custom_search_url": "https://duckduckgo.com/?q=%s",
            "gpu_acceleration": False, "ai_provider": "auto", "ai_api_url": "", "ai_model": "", "ai_api_key": "",
            "proxy_enabled": False, "use_bridges": False, "bridge_lines": "", "pause_history": False,
            "burn_animation": "blackhole", "clear_on_exit": False, "adblock_enabled": True,
            "cookies_enabled": "all", "javascript_enabled": True
        }
        self.data = self.load()

    def load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "r") as f: return {**self.defaults, **json.load(f)}
            except: pass
        return self.defaults.copy()

    def save(self):
        with open(self.file, "w") as f: json.dump(self.data, f, indent=2)

    def get(self, key, default=None):
        if key in self.data: return self.data[key]
        if key in self.defaults: return self.defaults[key]
        return default

    def set(self, key, value):
        self.data[key] = value
        self.save()

settings_mgr = SettingsManager()

# ==========================================
# 2. BLOCKLIST MANAGER (HOSTS FORMAT)
# ==========================================
HOSTS_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
MAX_LIST_SIZE = 50 * 1024 * 1024  # 50 MB limit
UPDATE_INTERVAL_DAYS = 3
DOMAIN_REGEX = re.compile(r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$')

# Hardcoded kill-list for guaranteed blocking of major ad networks (especially Google)
HARDCODED_ADBLOCK_DOMAINS = {
    "doubleclick.net", "googleads.g.doubleclick.net", "pagead2.googlesyndication.com",
    "googlesyndication.com", "google-analytics.com", "googletagmanager.com",
    "facebook.net", "connect.facebook.net", "scorecardresearch.com",
    "amazon-adsystem.com", "taboola.com", "outbrain.com", "adnxs.com",
    "criteo.com", "pubmatic.com", "rubiconproject.com", "casalemedia.com",
    "openx.net", "moatads.com", "adsrvr.org", "quantserve.com",
    "adservice.google.com", "ads.google.com", "partner.googleadservices.com",
    "googletagservices.com", "afcdn.net", "buysellads.com", "carbonads.net"
}

class BlocklistManager:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = self.dir / "blocklist.txt"
        self.allowlist_file = self.dir / "allowlist.txt"
        
        self.domains = set()
        self.allowlist = set()
        self.block_log = []
        self.max_log_size = 1000
        
        self.load_lists()
        
    def load_lists(self):
        if self.file.exists():
            self._parse_hosts_file(self.file, self.domains)
            
        if self.allowlist_file.exists():
            try:
                with open(self.allowlist_file, "r", encoding="utf-8") as f:
                    for line in f:
                        domain = line.strip().lower()
                        if domain and DOMAIN_REGEX.match(domain):
                            self.allowlist.add(domain)
            except: pass
            
    def _parse_hosts_file(self, filepath, target_set):
        target_set.clear()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if not parts:
                        continue
                        
                    start_idx = 0
                    if parts[0] in ("0.0.0.0", "127.0.0.1", "255.255.255.255", "::1"):
                        start_idx = 1
                        
                    for i in range(start_idx, len(parts)):
                        domain = parts[i].lower()
                        if domain.endswith('.'):
                            domain = domain[:-1]
                            
                        if DOMAIN_REGEX.match(domain) and '.' in domain:
                            target_set.add(domain)
        except Exception as e:
            print(f"[Blocklist] Error parsing {filepath}: {e}")

    def is_blocked(self, url_str, resource_type="unknown"):
        if not settings_mgr.get("adblock_enabled"):
            return False
            
        parsed = urlparse(url_str)
        host = parsed.hostname
        if not host:
            return False
            
        host = host.lower()
        if host.endswith('.'):
            host = host[:-1]
            
        if self._is_in_list(host, self.allowlist):
            return False
            
        # Check hardcoded kill-list first for guaranteed blocking
        if self._is_in_list(host, HARDCODED_ADBLOCK_DOMAINS):
            self._add_to_log(host, url_str, resource_type)
            return True
            
        if self._is_in_list(host, self.domains):
            self._add_to_log(host, url_str, resource_type)
            return True
            
        return False
        
    def _is_in_list(self, host, domain_list):
        if host in domain_list:
            return True
        parts = host.split('.')
        for i in range(1, len(parts)):
            parent = '.'.join(parts[i:])
            if parent in domain_list:
                return True
        return False

    def _add_to_log(self, host, url, rtype):
        entry = {"time": time.time(), "domain": host, "url": url, "type": rtype}
        self.block_log.append(entry)
        if len(self.block_log) > self.max_log_size:
            self.block_log.pop(0)
            
    def add_to_allowlist(self, domain):
        domain = domain.lower().strip()
        if DOMAIN_REGEX.match(domain):
            self.allowlist.add(domain)
            self._save_allowlist()
            
    def remove_from_allowlist(self, domain):
        domain = domain.lower().strip()
        if domain in self.allowlist:
            self.allowlist.remove(domain)
            self._save_allowlist()
            
    def _save_allowlist(self):
        try:
            with open(self.allowlist_file, "w", encoding="utf-8") as f:
                for d in sorted(self.allowlist):
                    f.write(d + "\n")
        except Exception as e:
            print(f"[Blocklist] Error saving allowlist: {e}")
            
    def clear_log(self):
        self.block_log.clear()
        
    def get_log(self):
        return list(reversed(self.block_log))

    def needs_update(self):
        if not self.file.exists():
            return True
        mtime = self.file.stat().st_mtime
        return (time.time() - mtime) > (UPDATE_INTERVAL_DAYS * 86400)

class BlocklistUpdater(QThread):
    update_finished = pyqtSignal(bool, str)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def run(self):
        try:
            temp_file = self.manager.file.with_suffix(".tmp")
            response = requests.get(HOSTS_URL, stream=True, timeout=15)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > MAX_LIST_SIZE:
                self.update_finished.emit(False, "Blocklist exceeds maximum size limit.")
                return
                
            downloaded_size = 0
            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if downloaded_size > MAX_LIST_SIZE:
                            raise ValueError("Downloaded file exceeds size limit")
                            
            if downloaded_size < 1024:
                raise ValueError("Downloaded file is too small to be valid")
                
            test_set = set()
            self.manager._parse_hosts_file(temp_file, test_set)
            
            if len(test_set) < 1000:
                raise ValueError("Parsed list contains too few domains")
                
            if self.manager.file.exists():
                self.manager.file.unlink()
            temp_file.rename(self.manager.file)
            
            self.manager._parse_hosts_file(self.manager.file, self.manager.domains)
            self.update_finished.emit(True, f"Successfully updated blocklist ({len(self.manager.domains)} domains).")
            
        except Exception as e:
            temp_file = self.manager.file.with_suffix(".tmp")
            if temp_file.exists():
                try: temp_file.unlink()
                except: pass
            self.update_finished.emit(False, f"Update failed: {str(e)}")

blocklist_mgr = BlocklistManager(settings_mgr.dir)

# ==========================================
# 3. ICON MANAGER
# ==========================================
class IconManager:
    def __init__(self):
        self.cache = {}
        self.icon_dir = SCRIPT_DIR / "data" / "images"
        self.fallbacks = {
            "back": "◀", "forward": "▶", "close": "✕", "refresh": "⟳", "settings": "⚙", "more": "⋮", 
            "extension": "🧩", "code": "🤖", "info": "ⓘ", "secure": "🔒", "insecure": "⚠", "add": "+",
            "dark": "🌙", "light": "☀", "system": "💻", "warning": "⚠", "minimize": "—", "maximize": "❐", 
            "home": "⌂", "loading": "⟳", "tools": "🛠", "private": "🕵", "newwindow": "⊞"
        }
        
    def get_path(self, name):
        path = self.icon_dir / f"{name}.svg"
        if path.exists(): return path.as_posix()
        return None

    def get_icon(self, name):
        path = self.get_path(name)
        if path: return QIcon(path)
        return None

icon_mgr = IconManager()

# ==========================================
# 4. TEMPLATE MANAGER
# ==========================================
class TemplateManager:
    def __init__(self):
        self.template_dir = SCRIPT_DIR / "data" / "templates"
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_templates()

    def _ensure_templates(self):
        templates = {
            "crash.html": """<!DOCTYPE html><html><head><style>
                body { font-family: sans-serif; background: #1a1a1a; color: #f0f0f0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                h1 { font-size: 48px; color: #ff3b30; }
                button { padding: 12px 24px; font-size: 16px; background: #1c4b82; color: white; border: none; border-radius: 8px; cursor: pointer; margin-top: 20px; }
            </style></head><body>
                <h1>Oops, this tab crashed</h1>
                <p>An error occurred while rendering this page.</p>
                <button onclick="window.location.reload()">Reload Tab</button>
            </body></html>"""
        }
        for name, content in templates.items():
            path = self.template_dir / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    def get_template(self, name):
        path = self.template_dir / name
        if path.exists():
            return path.read_text(encoding="utf-8")
        return "<html><body>Template missing</body></html>"

template_mgr = TemplateManager()

# ==========================================
# 5. CHROMIUM HARDENING FLAGS
# ==========================================
flags = [
    "--disable-dev-shm-usage", "--disable-software-rasterizer",
    "--disable-features=CalculateNativeWinOcclusion,msaa-intrinsics",
    "--disable-breakpad", "--disable-client-side-phishing-detection",
    "--no-pings", "--disable-background-networking",
    "--enable-features=EncryptedClientHello,HttpsOnlyMode",
    "--blink-settings=hardwareConcurrency=8,deviceMemory=8"
]

if settings_mgr.get("proxy_enabled"):
    flags.append('--proxy-server="socks5://127.0.0.1:9050"')
    flags.append('--host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"')
else:
    flags.append("--enable-features=DnsOverHttps")
    flags.append("--dns-over-https=https://cloudflare-dns.com/dns-query")

if not settings_mgr.get("gpu_acceleration"): flags.append("--disable-gpu")
if settings_mgr.get("cookies_enabled") == "third-party": flags.append("--block-third-party-cookies")
    
exts = settings_mgr.get("extensions")
if exts:
    abs_exts = [os.path.abspath(p).replace("\\", "\\\\") for p in exts if os.path.exists(p)]
    if abs_exts: flags.append("--load-extension=" + ",".join(abs_exts))
        
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)

# ==========================================
# 6. SEARCH ENGINES & AI PROVIDERS
# ==========================================
SEARCH_ENGINES = {
    "duckduckgo": "https://duckduckgo.com/?q=%s", "google": "https://www.google.com/search?q=%s",
    "bing": "https://www.bing.com/search?q=%s", "brave": "https://search.brave.com/search?q=%s",
    "ecosia": "https://www.ecosia.org/search?q=%s", "startpage": "https://www.startpage.com/do/dsearch?query=%s",
    "custom": settings_mgr.get("custom_search_url")
}

def get_search_url():
    engine = settings_mgr.get("search_engine")
    if engine == "custom": return settings_mgr.get("custom_search_url")
    return SEARCH_ENGINES.get(engine, SEARCH_ENGINES["duckduckgo"])

AI_PROVIDERS = {
    "auto": "Auto-detect", "ollama": "Ollama (Local)", "lmstudio": "LM Studio (Local)",
    "jan": "Jan (Local)", "openai": "OpenAI", "anthropic": "Anthropic (Claude)",
    "gemini": "Google Gemini", "huggingface": "HuggingFace", "custom": "Custom API"
}

# ==========================================
# 7. INTEGRATED TOR MANAGER (CROSS-PLATFORM + ARM64)
# ==========================================
class TorManager:
    def __init__(self):
        self.process = None
        self.system = platform.system()
        self.machine = platform.machine()
        
        # Auto-detect OS and Architecture to set correct paths
        if self.system == "Windows":
            self.tor_dir = SCRIPT_DIR / "tor-win-x86_64" / "tor"
            self.tor_exe = self.tor_dir / "tor.exe"
            self.lyrebird_name = "lyrebird.exe"
            self.obfs4_name = "obfs4proxy.exe"
            self.snowflake_name = "snowflake-client.exe"
            self.meek_name = "meek-client.exe"
        elif self.system == "Darwin": # macOS
            # Detect Apple Silicon (ARM64) vs Intel (x86_64)
            if self.machine in ("arm64", "aarch64"):
                self.tor_dir = SCRIPT_DIR / "tor-macos-aarch64" / "tor"
            else:
                self.tor_dir = SCRIPT_DIR / "tor-macos-x86_64" / "tor"
            self.tor_exe = self.tor_dir / "tor"
            self.lyrebird_name = "lyrebird"
            self.obfs4_name = "obfs4proxy"
            self.snowflake_name = "snowflake-client"
            self.meek_name = "meek-client"
        else: # Linux and others
            self.tor_dir = SCRIPT_DIR / "tor-gnu-linux-x86_64" / "tor"
            self.tor_exe = self.tor_dir / "tor"
            self.lyrebird_name = "lyrebird"
            self.obfs4_name = "obfs4proxy"
            self.snowflake_name = "snowflake-client"
            self.meek_name = "meek-client"
            
        self.torrc_path = Path(settings_mgr.dir) / "torrc"
        
    def find_executable(self, name):
        search_dirs = [
            self.tor_dir / "pluggable_transports",
            self.tor_dir / "PluggableTransports",
            self.tor_dir.parent / "pluggable_transports",
            self.tor_dir.parent / "PluggableTransports"
        ]
        for d in search_dirs:
            if d.exists():
                p = d / name
                if p.exists():
                    return str(p)
                for root, dirs, files in os.walk(d):
                    if name in files: 
                        return os.path.join(root, name)
        return None

    def write_torrc(self, use_bridges, bridge_lines):
        config = ["SOCKSPort 9050", "ControlPort 9051", "CookieAuthentication 0"]
        
        lyrebird_path = self.find_executable(self.lyrebird_name)
        obfs4_path = self.find_executable(self.obfs4_name)
        snowflake_path = self.find_executable(self.snowflake_name)
        meek_path = self.find_executable(self.meek_name)
        
        available_transports = []
        
        if lyrebird_path:
            config.append(f'ClientTransportPlugin obfs4 exec "{lyrebird_path}"')
            config.append(f'ClientTransportPlugin meek_lite exec "{lyrebird_path}"')
            config.append(f'ClientTransportPlugin snowflake exec "{lyrebird_path}"')
            available_transports.extend(["obfs4", "meek_lite", "snowflake"])
        else:
            if obfs4_path:
                config.append(f'ClientTransportPlugin obfs4 exec "{obfs4_path}"')
                available_transports.append("obfs4")
            if snowflake_path:
                config.append(f'ClientTransportPlugin snowflake exec "{snowflake_path}"')
                available_transports.append("snowflake")
            if meek_path:
                config.append(f'ClientTransportPlugin meek exec "{meek_path}"')
                available_transports.extend(["meek", "meek_lite"])
                
        if use_bridges and bridge_lines.strip():
            valid_bridges = []
            for line in bridge_lines.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'): continue
                
                if "meek_lite" in available_transports and "meek" not in available_transports:
                    if "Bridge meek " in line: line = line.replace("Bridge meek ", "Bridge meek_lite ", 1)
                    elif line.startswith("meek "): line = "meek_lite " + line[5:]
                    elif " meek " in line: line = line.replace(" meek ", " meek_lite ", 1)
                    
                if not line.lower().startswith("bridge "):
                    line = f"Bridge {line}"
                    
                valid_bridges.append(line)
                
            if valid_bridges:
                config.append("UseBridges 1")
                config.extend(valid_bridges)
                    
        with open(self.torrc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(config))
            
    def start(self, use_bridges, bridge_lines):
        self.stop()
        try:
            if self.system == 'Windows':
                subprocess.run(['taskkill', '/F', '/IM', 'tor.exe'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(['pkill', '-9', 'tor'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
        
        if not self.tor_exe.exists():
            print(f"[Tor Manager] Executable not found at {self.tor_exe}")
            return
            
        # Ensure executable permissions on Unix-like systems (macOS/Linux)
        if self.system != "Windows":
            try:
                os.chmod(self.tor_exe, 0o755)
                for pt in [self.find_executable(self.lyrebird_name), self.find_executable(self.obfs4_name), 
                           self.find_executable(self.snowflake_name), self.find_executable(self.meek_name)]:
                    if pt and os.path.exists(pt):
                        os.chmod(pt, 0o755)
            except Exception as e:
                print(f"[Tor Manager] Failed to set executable permissions: {e}")
            
        self.write_torrc(use_bridges, bridge_lines)
        
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if self.system == 'Windows' else 0
            self.process = subprocess.Popen(
                [str(self.tor_exe), "-f", str(self.torrc_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags
            )
            print(f"[Tor Manager] Subprocess started on port 9050.")
        except Exception as e:
            print(f"[Tor Manager] Failed to start: {e}")
            
    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except: self.process.kill()
            self.process = None

    def new_circuit(self):
        if not self.process: return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", 9051))
            s.send(b"AUTHENTICATE\r\n")
            if b"250 OK" in s.recv(1024):
                s.send(b"SIGNAL NEWNYM\r\n")
                s.recv(1024)
                s.close()
                return True
            s.close()
        except: pass
        return False

    def fetch_moat_bridges(self, transport="obfs4"):
        try:
            url = "https://bridges.torproject.org/moat/circumvention/defaut"
            payload = {"transport": transport}
            headers = {"Content-Type": "application/json"}
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if "data" in data and len(data["data"]) > 0:
                    bridges = []
                    for item in data["data"]:
                        if "bridges" in item:
                            bridges.extend(item["bridges"])
                    return "\n".join(bridges)
            return None
        except Exception as e:
            print(f"[Moat] Failed to fetch bridges: {e}")
            return None

tor_manager = TorManager()

# ==========================================
# 8. TOR PORT CHECKER & STATUS BAR
# ==========================================
class TorPortChecker(QThread):
    tor_ready = pyqtSignal()
    tor_failed = pyqtSignal()

    def __init__(self, port=9050, timeout=30):
        super().__init__()
        self.port = port
        self.timeout = timeout

    def run(self):
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                s.connect(("127.0.0.1", self.port))
                s.close()
                self.tor_ready.emit()
                return
            except: time.sleep(0.5)
        self.tor_failed.emit()

class TorStatusBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        self.label = QLabel("Connecting to Tor...")
        self.label.setStyleSheet("font-size: 12px;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(80)
        self.progress.setFixedHeight(10)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        layout.addStretch()
        
        self.size_grip = QSizeGrip(self)
        layout.addWidget(self.size_grip)
        
        self.hide()

# ==========================================
# 9. AI MODEL DETECTION
# ==========================================
class AIModelDetector(QThread):
    models_detected = pyqtSignal(list)

    def run(self):
        models = []
        endpoints = [("Ollama", "http://localhost:11434/api/tags"), ("LM Studio", "http://localhost:1234/v1/models"), ("Jan", "http://localhost:1337/v1/models")]
        for provider, url in endpoints:
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    if provider == "Ollama":
                        for model in data.get("models", []): models.append((model.get("name", "unknown"), "http://localhost:11434/api/generate", model.get("name"), "ollama"))
                    else:
                        for model in data.get("data", []): models.append((model.get("id", "unknown"), f"{url.rsplit('/v1/', 1)[0]}/v1/chat/completions", model.get("id"), "openai"))
            except: pass
        self.models_detected.emit(models)

# ==========================================
# 10. THEME MANAGER
# ==========================================
class ThemeManager:
    @staticmethod
    def get_colors(theme, accent, is_system_dark):
        is_dark = (theme == "dark") or (theme == "system" and is_system_dark)
        if is_dark:
            return {"bg": "#1a1a1a", "surface": "#2d2d2d", "text": "#f0f0f0", "text_secondary": "#b0b0b0", "border": "#3d3d3d", "hover": "#353535", "accent": accent, "input_bg": "#353535"}
        return {"bg": "#f5f5f7", "surface": "#ffffff", "text": "#1d1d1f", "text_secondary": "#6e6e73", "border": "#d2d2d7", "hover": "#e8e8ed", "accent": accent, "input_bg": "#ffffff"}

# ==========================================
# 11. PRIVACY INTERCEPTOR
# ==========================================
# Updated to Chrome 154 and Firefox 135 for modern compatibility
BRANDED_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 JosephBrowser/2026.10.08"
FIREFOX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"

class PrivacyInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        info.setHttpHeader(b"DNT", b"1")
        info.setHttpHeader(b"Sec-GPC", b"1")
        
        url = info.requestUrl().toString().lower()
        host = info.requestUrl().host().lower()
        
        if "accounts.google.com" in host or "google.com" in host:
            info.setHttpHeader(b"User-Agent", FIREFOX_UA.encode())
        else:
            info.setHttpHeader(b"User-Agent", BRANDED_UA.encode())
            
        if settings_mgr.get("adblock_enabled"):
            res_type = info.resourceType()
            if blocklist_mgr.is_blocked(url, str(res_type)):
                info.block(True)
                return

# ==========================================
# 12. SPINNING LOADING INDICATOR
# ==========================================
class SpinningLabel(QLabel):
    def __init__(self, svg_path):
        super().__init__()
        self.svg_path = svg_path
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.spin)
        self.setFixedSize(24, 24)
        self.hide()
        self.use_svg = False
        try:
            from PyQt6.QtSvg import QSvgRenderer
            if svg_path and Path(svg_path).exists():
                self.renderer = QSvgRenderer(svg_path)
                if self.renderer.isValid(): self.use_svg = True
        except: pass

    def start(self):
        self.show()
        self.timer.start(30)
        
    def stop(self):
        self.timer.stop()
        self.hide()
        
    def spin(self):
        self.angle = (self.angle + 25) % 360
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(12, 12)
        painter.rotate(self.angle)
        painter.translate(-12, -12)
        if self.use_svg:
            self.renderer.render(painter)
        else:
            painter.setPen(QPen(QColor(100, 100, 100), 2))
            painter.drawText(4, 18, "⟳")
        painter.end()
        self.setPixmap(pixmap)

# ==========================================
# 13. BURN ANIMATION JS
# ==========================================
def get_burn_js(anim_type, burn_type):
    if anim_type == "blackhole":
        return f"""(() => {{ const style = document.createElement('style'); style.innerHTML = `@keyframes joseph-suck {{ 0% {{ transform: scale(1) rotate(0deg); filter: blur(0); opacity: 1; }} 100% {{ transform: scale(0.01) rotate(1080deg); filter: blur(20px); opacity: 0; }} }} body {{ animation: joseph-suck 2s forwards ease-in !important; transform-origin: center center !important; overflow: hidden !important; }} #joseph-blackhole {{ position: fixed; top: 50%; left: 50%; width: 10px; height: 10px; background: black; border-radius: 50%; z-index: 999999; box-shadow: 0 0 50px 20px black; animation: joseph-bh-grow 2s forwards ease-in; transform: translate(-50%, -50%); }} @keyframes joseph-bh-grow {{ 0% {{ width: 10px; height: 10px; }} 100% {{ width: 200vmax; height: 200vmax; }} }}`; (document.head || document.documentElement).appendChild(style); const bh = document.createElement('div'); bh.id = 'joseph-blackhole'; document.body.appendChild(bh); setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000); }})();"""
    elif anim_type == "shredder":
        return f"""(() => {{ const style = document.createElement('style'); style.innerHTML = `@keyframes joseph-shred {{ 0% {{ transform: translateY(0) rotate(0); opacity: 1; }} 100% {{ transform: translateY(150vh) rotate(var(--rot)); opacity: 0; }} }}`; (document.head || document.documentElement).appendChild(style); const html = document.body.innerHTML; document.body.innerHTML = ''; document.body.style.margin = '0'; document.body.style.overflow = 'hidden'; for(let i=0; i<20; i++) {{ const strip = document.createElement('div'); const rot = (Math.random() - 0.5) * 60; strip.style.cssText = `position:absolute; top:${{i*5}}vh; left:0; width:100%; height:5vh; overflow:hidden; --rot: ${{rot}}deg; animation: joseph-shred 1.5s forwards ease-in ${{Math.random()*0.5}}s;`; strip.innerHTML = `<div style="position:absolute; top:-${{i*5}}vh; left:0; width:100%; height:100vh;">${{html}}</div>`; document.body.appendChild(strip); }} setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000); }})();"""
    elif anim_type == "incinerator":
        return f"""(() => {{ const style = document.createElement('style'); style.innerHTML = `@keyframes joseph-burn {{ 0% {{ filter: brightness(1); }} 20% {{ filter: brightness(1.5) sepia(1) hue-rotate(-30deg); }} 100% {{ filter: brightness(0) blur(10px); opacity: 0; }} }} body {{ animation: joseph-burn 2s forwards ease-in !important; overflow: hidden !important; }}`; (document.head || document.documentElement).appendChild(style); setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000); }})();"""
    elif anim_type == "explode":
        return f"""(() => {{
            const style = document.createElement('style');
            style.innerHTML = `
                @keyframes joseph-explode {{
                    0% {{ transform: translate(0, 0) rotate(0deg) scale(1); opacity: 1; }}
                    100% {{ transform: translate(var(--tx), var(--ty)) rotate(var(--rot)) scale(0.2); opacity: 0; }}
                }}
            `;
            (document.head || document.documentElement).appendChild(style);
            const elements = document.body.querySelectorAll('*');
            elements.forEach(el => {{
                const tx = (Math.random() - 0.5) * 2500;
                const ty = (Math.random() - 0.5) * 2500;
                const rot = (Math.random() - 0.5) * 1080;
                el.style.setProperty('--tx', tx + 'px');
                el.style.setProperty('--ty', ty + 'px');
                el.style.setProperty('--rot', rot + 'deg');
                el.style.animation = `joseph-explode ${{1 + Math.random() * 0.5}}s forwards ease-in`;
                el.style.transformOrigin = 'center center';
            }});
            setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000);
        }})();"""

# ==========================================
# 14. WEB TAB & STEALTH
# ==========================================
class WebPage(QWebEnginePage):
    def __init__(self, profile, parent, main_window):
        super().__init__(profile, parent)
        self.main_window = main_window

    def createWindow(self, type):
        new_tab = self.main_window.add_new_tab(QUrl("about:blank"))
        return new_tab.page()
        
    def acceptNavigationRequest(self, url, type, isMainFrame):
        if url.scheme() == "josephbrowser":
            QTimer.singleShot(0, lambda: self.main_window.load_internal_page(url.toString(), new_tab=True))
            return False
        return True

class WebTab(QWebEngineView):
    def __init__(self, main_window, profile=None):
        super().__init__()
        self.main_window = main_window
        
        if profile is None:
            profile = QWebEngineProfile.defaultProfile()
            
        self.setPage(WebPage(profile, self, main_window))
        
        self.renderProcessTerminated.connect(self.handle_crash)
        
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, settings_mgr.get("javascript_enabled"))
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        
        cookie_mode = settings_mgr.get("cookies_enabled")
        if cookie_mode == "none":
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)
        
        script = QWebEngineScript()
        script.setSourceCode("""(() => { 
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); 
            Object.defineProperty(navigator, 'getBattery', {value: () => Promise.resolve({charging: true, level: 1})}); 
            Object.defineProperty(screen, 'width', {get: () => 1920}); 
            Object.defineProperty(screen, 'height', {get: () => 1080}); 
            window.RTCPeerConnection = undefined; 
            
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                if (type === 'image/png' || type === undefined) {
                    const context = this.getContext('2d');
                    if (context) {
                        const imageData = context.getImageData(0, 0, this.width, this.height);
                        for (let i = 0; i < imageData.data.length; i += 4) {
                            imageData.data[i] += Math.floor(Math.random() * 2);
                            imageData.data[i+1] += Math.floor(Math.random() * 2);
                            imageData.data[i+2] += Math.floor(Math.random() * 2);
                        }
                        context.putImageData(imageData, 0, 0);
                    }
                }
                return origToDataURL.apply(this, arguments);
            };
        })();""")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        try: script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        except: script.setWorldId(0)
        self.page().profile().scripts().insert(script)
        
        if settings_mgr.get("adblock_enabled"):
            adblock_script = QWebEngineScript()
            # Enhanced AdBlocker with aggressive CSS hiding and DOM removal for Google Ads and other networks
            adblock_script.setSourceCode("""
(() => {
    if (!document.documentElement) return;
    const target = document.head || document.documentElement;
    const style = document.createElement('style');
    style.innerHTML = `
        /* Generic Ad Selectors */
        [id*="ad-"], [class*="ad-"], [id*="ads-"], [class*="ads-"],
        [id*="advert"], [class*="advert"], [id*="banner-ad"], [class*="banner-ad"],
        div[data-ad], div[aria-label*="Ad"], div[aria-label*="advertisement"],
        .adsbygoogle, .ad-container, .ad-wrapper, .ad-banner, .ad-slot,
        ins.adsbygoogle, [id^="google_ads"], [class^="google_ads"],
        [id*="gpt-ad"], [class*="gpt-ad"], [id*="dfp-ad"], [class*="dfp-ad"],
        [id*="taboola"], [class*="taboola"], [id*="outbrain"], [class*="outbrain"],
        [id*="carbonads"], [class*="carbonads"], [id*="buysellads"], [class*="buysellads"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            width: 0 !important;
            position: absolute !important;
            left: -9999px !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
        
        /* Hide common ad iframes */
        iframe[src*="doubleclick"], iframe[src*="googleads"], iframe[src*="adnxs"],
        iframe[src*="googlesyndication"], iframe[src*="pagead"], iframe[src*="facebook.com/plugins"],
        iframe[src*="amazon-adsystem"], iframe[src*="taboola"], iframe[src*="outbrain"],
        iframe[src*="carbonads"], iframe[src*="buysellads"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            width: 0 !important;
            position: absolute !important;
            left: -9999px !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }
    `;
    target.appendChild(style);
    
    const removeAds = () => {
        const selectors = [
            'iframe[src*="doubleclick"]', 'iframe[src*="googleads"]', 'iframe[src*="googlesyndication"]',
            'iframe[src*="pagead"]', 'iframe[src*="adnxs"]', 'iframe[src*="taboola"]',
            'ins.adsbygoogle', '.adsbygoogle', '[id*="google_ads"]', '[class*="gpt-ad"]',
            '[id*="carbonads"]', '[class*="carbonads"]'
        ];
        document.querySelectorAll(selectors.join(',')).forEach(el => {
            el.remove();
        });
    };
    
    removeAds();
    const observer = new MutationObserver(removeAds);
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            if (document.body) observer.observe(document.body, { childList: true, subtree: true });
        });
    }
})();
            """)
            adblock_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            try: adblock_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            except: adblock_script.setWorldId(0)
            self.page().profile().scripts().insert(adblock_script)

    def handle_crash(self, status, exit_code):
        print(f"[Crash] Render process terminated: {status}, exit code: {exit_code}")
        crash_html = template_mgr.get_template("crash.html")
        self.page().setHtml(crash_html, QUrl("josephbrowser://crash"))
        
    def handle_title_change(self, title):
        # CRITICAL SECURITY: Only accept IPC commands from internal sandboxed pages
        if self.url().scheme() != "josephbrowser":
            return
            
        if title.startswith("CMD:"):
            parts = title.split(":", 2)
            if len(parts) >= 2:
                cmd = parts[1]
                args = [unquote(parts[2])] if len(parts) > 2 else []
                self.main_window.execute_command(cmd, args, self)
            self.page().runJavaScript("document.title = 'Joseph Browser';")

# ==========================================
# 15. AI SIDEBAR
# ==========================================
class AISidebar(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(QLabel("<b>AI Assistant</b>"))
        
        self.model_combo = QComboBox()
        self.model_combo.addItem("Detecting...")
        layout.addWidget(self.model_combo)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display, 1)
        
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask anything...")
        self.input_box.returnPressed.connect(self.send_message)
        layout.addWidget(self.input_box)

    def showEvent(self, event):
        super().showEvent(event)
        if self.model_combo.count() == 1: self.detect_models()

    def detect_models(self):
        self.model_combo.clear()
        self.model_combo.addItem("Detecting...")
        self.detector = AIModelDetector()
        self.detector.models_detected.connect(self.update_models)
        self.detector.start()

    def update_models(self, models):
        self.model_combo.clear()
        providers = {}
        for display_name, url, model_name, provider_type in models:
            if provider_type not in providers: providers[provider_type] = []
            providers[provider_type].append((display_name, url, model_name, provider_type))
        for p_type, p_models in providers.items():
            idx = self.model_combo.count()
            self.model_combo.addItem(f"── {p_type.upper()} ──")
            self.model_combo.model().item(idx).setEnabled(False)
            for d_name, url, m_name, pt in p_models:
                self.model_combo.addItem(d_name, (url, m_name, pt))
        idx = self.model_combo.count()
        self.model_combo.addItem("── CUSTOM ──")
        self.model_combo.model().item(idx).setEnabled(False)
        self.model_combo.addItem("Use Settings", ("custom", "", "custom"))

    def send_message(self):
        msg = self.input_box.text().strip()
        if not msg: return
        self.chat_display.append(f"<b>You:</b> {html_lib.escape(msg)}")
        self.input_box.clear()
        
        model_data = self.model_combo.currentData()
        if not model_data or model_data[0] == "custom":
            provider = settings_mgr.get("ai_provider")
            if provider == "auto" or provider == "custom": url, model_name, provider_type = settings_mgr.get("ai_api_url"), settings_mgr.get("ai_model"), "custom"
            else: url, model_name, provider_type, _ = self.get_provider_config(provider)
        else: url, model_name, provider_type = model_data

        if not url or not model_name:
            self.chat_display.append("<i>Configure AI in Settings.</i>")
            return

        try:
            headers = {"Authorization": f"Bearer {settings_mgr.get('ai_api_key')}"} if settings_mgr.get("ai_api_key") else {}
            if provider_type == "ollama":
                response = requests.post(url, json={"model": model_name, "prompt": msg, "stream": False}, headers=headers, timeout=120)
                ai_msg = response.json().get("response", str(response.json()))
            else:
                response = requests.post(url, json={"model": model_name, "messages": [{"role": "user", "content": msg}]}, headers=headers, timeout=120)
                ai_msg = response.json().get("choices", [{}])[0].get("message", {}).get("content", str(response.json()))
            self.chat_display.append(f"<b>AI:</b> {html_lib.escape(ai_msg)}")
        except Exception as e:
            self.chat_display.append(f"<i>Error: {str(e)}</i>")

    def get_provider_config(self, provider):
        configs = {"ollama": ("http://localhost:11434/api/generate", "llama3", "ollama", ""), "openai": ("https://api.openai.com/v1/chat/completions", "gpt-3.5-turbo", "openai", settings_mgr.get("ai_api_key"))}
        return configs.get(provider, ("", "", "custom", ""))

# ==========================================
# 16. TOOLS SIDEBAR
# ==========================================
class ToolsSidebar(QFrame):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setFixedWidth(320)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { padding: 8px 16px; } QTabWidget::pane { border: none; }")
        self.layout.addWidget(self.tabs)
        
        self.setup_calculator()
        self.ai_sidebar = AISidebar(main_window)
        self.tabs.addTab(self.ai_sidebar, "AI")
        self.setup_source()
        
        self.hide()

    def setup_calculator(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.calc_display = QLineEdit("0")
        self.calc_display.setReadOnly(True)
        self.calc_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.calc_display.setStyleSheet("font-size: 24px; padding: 10px;")
        layout.addWidget(self.calc_display)
        
        grid = QGridLayout()
        buttons = [('7',0,0),('8',0,1),('9',0,2),('/',0,3),('4',1,0),('5',1,1),('6',1,2),('*',1,3),('1',2,0),('2',2,1),('3',2,2),('-',2,3),('0',3,0),('.',3,1),('=',3,2),('+',3,3),('C',4,0)]
        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.setFixedSize(60, 40)
            btn.clicked.connect(lambda checked, t=text: self.calc_click(t))
            grid.addWidget(btn, row, col)
        layout.addLayout(grid)
        self.tabs.addTab(tab, "Calculator")

    def calc_click(self, char):
        if char == 'C': self.calc_display.setText('0')
        elif char == '=':
            try: self.calc_display.setText(str(eval(self.calc_display.text())))
            except: self.calc_display.setText('Error')
        else:
            if self.calc_display.text() == '0' and char != '.': self.calc_display.setText(char)
            else: self.calc_display.setText(self.calc_display.text() + char)

    def setup_source(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.source_text = QTextEdit()
        self.source_text.setReadOnly(True)
        self.source_text.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(self.source_text)
        btn = QPushButton("Refresh Source")
        btn.clicked.connect(self.refresh_source)
        layout.addWidget(btn)
        self.tabs.addTab(tab, "Source")

    def refresh_source(self):
        tab = self.main_window.current_tab()
        if tab: tab.page().toHtml(self.source_text.setPlainText)

# ==========================================
# 17. HELPER FUNCTIONS
# ==========================================
def create_icon_btn(name, size=36):
    btn = QPushButton()
    icon = icon_mgr.get_icon(name)
    if icon:
        btn.setIcon(icon)
        btn.setIconSize(QSize(20, 20))
    else:
        btn.setText(icon_mgr.fallbacks.get(name, "?"))
        btn.setStyleSheet("font-size: 16px; font-weight: bold;")
    btn.setFixedSize(size, size)
    return btn

def generate_home_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    search_url = get_search_url()
    return f"""<!DOCTYPE html><html><head><style>body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; margin: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }} .logo {{ font-size: 64px; font-weight: 700; color: {c['accent']}; margin-bottom: 40px; }} .search-box input {{ width: 600px; padding: 16px 24px; font-size: 18px; border: 2px solid {c['border']}; border-radius: 50px; background: {c['surface']}; color: {c['text']}; }} .shortcuts {{ display: flex; gap: 16px; margin-top: 40px; }} .shortcut {{ padding: 12px 24px; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; text-decoration: none; color: {c['text']}; }}</style></head><body><div class="logo">Joseph</div><form class="search-box" onsubmit="window.location.href='{search_url}'.replace('%s', encodeURIComponent(document.getElementById('search').value)); return false;"><input type="text" id="search" placeholder="Search the web..." autofocus></form><div class="shortcuts"><a href="https://duckduckgo.com" class="shortcut">DuckDuckGo</a><a href="josephbrowser://settings" class="shortcut">Settings</a></div></body></html>"""

def generate_settings_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    exts = settings_mgr.get("extensions")
    ext_list = "".join([f"<div class='ext-item'><span>{Path(ext).name}</span><button onclick=\"document.title='CMD:remove_ext:{ext}'\">Remove</button></div>" for ext in exts]) if exts else "<p class='empty'>No extensions installed</p>"
    search_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("search_engine")==k else ""}>{k.title()}</option>' for k in SEARCH_ENGINES.keys()])
    provider_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("ai_provider")==k else ""}>{v}</option>' for k, v in AI_PROVIDERS.items()])
    anim_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("burn_animation")==k else ""}>{k.title()}</option>' for k in ["blackhole", "incinerator", "shredder", "explode"]])
    cookie_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("cookies_enabled")==k else ""}>{v}</option>' for k, v in [("all", "Allow All Cookies"), ("third-party", "Block Third-Party Only"), ("none", "Block All Cookies")]])
    
    checks = {k: "checked" if settings_mgr.get(k) else "" for k in ["proxy_enabled", "use_bridges", "gpu_acceleration", "pause_history", "clear_on_exit", "adblock_enabled", "javascript_enabled"]}

    return f"""<!DOCTYPE html><html><head><style>* {{ box-sizing: border-box; margin: 0; padding: 0; }} body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; display: flex; height: 100vh; }} .sidebar {{ width: 250px; background: {c['surface']}; border-right: 1px solid {c['border']}; padding: 20px 0; }} .nav-btn {{ display: block; width: 100%; text-align: left; padding: 12px 24px; background: transparent; border: none; color: {c['text_secondary']}; font-size: 15px; cursor: pointer; }} .nav-btn.active {{ background: {c['accent']}; color: white; border-left: 4px solid {c['accent']}; }} main {{ flex: 1; padding: 40px; overflow-y: auto; }} h1 {{ font-size: 28px; margin-bottom: 32px; }} h2 {{ font-size: 20px; margin-bottom: 24px; color: {c['accent']}; border-bottom: 1px solid {c['border']}; padding-bottom: 12px; }} .card {{ background: {c['surface']}; padding: 24px; border-radius: 12px; border: 1px solid {c['border']}; margin-bottom: 24px; }} label {{ display: block; margin-bottom: 8px; font-weight: 500; color: {c['text_secondary']}; }} input, select, textarea {{ width: 100%; padding: 12px 16px; border: 1px solid {c['border']}; border-radius: 8px; background: {c['input_bg']}; color: {c['text']}; margin-bottom: 16px; }} .checkbox-row {{ display: flex; align-items: center; margin-bottom: 16px; }} button.primary {{ padding: 12px 24px; background: {c['accent']}; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }} .ext-item {{ display: flex; justify-content: space-between; align-items: center; padding: 12px; background: {c['input_bg']}; border-radius: 8px; margin-bottom: 8px; }} .ext-item button {{ padding: 6px 12px; background: #ff3b30; color: white; border: none; border-radius: 4px; cursor: pointer; }} .hint {{ color: {c['text_secondary']}; font-size: 13px; margin-top: 8px; }} section {{ display: none; }} section.active {{ display: block; }} .toggle {{ position: relative; display: inline-block; width: 46px; height: 24px; }} .toggle input {{ opacity: 0; width: 0; height: 0; }} .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: {c['border']}; transition: .4s; border-radius: 24px; }} .slider:before {{ position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }} input:checked + .slider {{ background-color: {c['accent']}; }} input:checked + .slider:before {{ transform: translateX(22px); }}</style></head><body><nav class="sidebar"><button class="nav-btn active" onclick="switchSection('general')">General</button><button class="nav-btn" onclick="switchSection('appearance')">Appearance</button><button class="nav-btn" onclick="switchSection('search')">Search</button><button class="nav-btn" onclick="switchSection('privacy')">Privacy & Security</button><button class="nav-btn" onclick="switchSection('ai')">AI Assistant</button><button class="nav-btn" onclick="switchSection('extensions')">Extensions</button><button class="nav-btn" onclick="switchSection('optimizations')">Optimizations</button><button class="nav-btn" onclick="switchSection('about')">About</button></nav><main><h1>Settings</h1><section id="general" class="active"><h2>General</h2><div class="card"><p>Joseph Browser v{BROWSER_VERSION}</p><div class="checkbox-row" style="margin-top:16px;"><label class="toggle"><input type="checkbox" id="pause_history" {checks['pause_history']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Pause History</label></div><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="clear_on_exit" {checks['clear_on_exit']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Clear Data on Exit</label></div><label>Shredding Animation</label><select id="burn_animation">{anim_options}</select></div></section><section id="appearance"><h2>Appearance</h2><div class="card"><label>Theme</label><select id="theme"><option value="system" {'selected' if settings_mgr.get('theme')=='system' else ''}>System</option><option value="light" {'selected' if settings_mgr.get('theme')=='light' else ''}>Light</option><option value="dark" {'selected' if settings_mgr.get('theme')=='dark' else ''}>Dark</option></select><label>Accent Color</label><input type="color" id="accent" value="{settings_mgr.get('accent')}"><label>Wallpaper URL</label><input type="text" id="wallpaper" value="{settings_mgr.get('wallpaper')}"></div></section><section id="search"><h2>Search</h2><div class="card"><label>Engine</label><select id="search_engine">{search_options}</select><label>Custom URL (%s)</label><input type="text" id="custom_search_url" value="{settings_mgr.get('custom_search_url')}"></div></section><section id="privacy"><h2>Privacy & Security</h2><div class="card"><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="adblock_enabled" {checks['adblock_enabled']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Enable Ad/Tracker Blocker</label></div><p class="hint">Removes ad containers from pages and blocks tracker domains.</p><button class="primary" onclick="window.location.href='josephbrowser://adblock'" style="margin-top:10px;">Ad Blocker Controls & Logs</button><label style="margin-top:20px;">Cookie Policy</label><select id="cookies_enabled">{cookie_options}</select><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="javascript_enabled" {checks['javascript_enabled']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Enable JavaScript</label></div><p class="hint">Disabling JavaScript may break some websites but improves security.</p></div><div class="card"><h3 style="color:{c['accent']}; margin-bottom:16px;">Tor Network</h3><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="proxy_enabled" {checks['proxy_enabled']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Enable Tor</label></div><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="use_bridges" {checks['use_bridges']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Use Bridges</label></div><label>Bridge Presets</label><select id="bridge_preset" onchange="setBridgePreset(this.value)"><option value="none">None</option><option value="obfs4">obfs4</option><option value="meek_lite">meek_lite</option><option value="snowflake">snowflake</option></select><label>Bridge Lines</label><textarea id="bridge_lines" rows="4" style="font-family:monospace;">{settings_mgr.get('bridge_lines')}</textarea><button class="primary" onclick="document.title='CMD:fetch_bridges:'" style="margin-top:10px;">Fetch Bridges (Moat)</button></div></section><section id="ai"><h2>AI</h2><div class="card"><label>Provider</label><select id="ai_provider" onchange="toggleCustomFields()">{provider_options}</select><div id="custom-fields"><label>API URL</label><input type="text" id="ai_api_url" value="{settings_mgr.get('ai_api_url')}"><label>Model</label><input type="text" id="ai_model" value="{settings_mgr.get('ai_model')}"><label>API Key</label><input type="password" id="ai_api_key" value="{settings_mgr.get('ai_api_key')}"></div></div></section><section id="extensions"><h2>Extensions</h2><div class="card"><div id="ext-list">{ext_list}</div><button class="primary" onclick="document.title='CMD:add_ext:'" style="margin-top:16px;">+ Add Extension</button></div></section><section id="optimizations"><h2>Optimizations</h2><div class="card"><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="gpu_acceleration" {checks['gpu_acceleration']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">GPU Acceleration</label></div></div></section><section id="about"><h2>About</h2><div class="card"><p style="font-size:24px; font-weight:700; color:{c['accent']};">Joseph Browser</p><p>Version: {BROWSER_VERSION}</p><p class="hint" style="margin-top:12px;"><b>Hotkeys:</b><br>Ctrl+Del: Shred site data.<br>Ctrl+Shift+Del: Burn session & new Tor IP.<br>F12: Panic Mode (Hide Window).</p></div></section><button class="primary" onclick="saveSettings()" style="position:fixed; bottom:40px; right:40px; padding:16px 32px; box-shadow:0 4px 12px rgba(0,0,0,0.2);">Save Settings</button></main><script>function switchSection(id) {{ document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active')); document.querySelector(`[onclick="switchSection('${{id}}')"]`).classList.add('active'); document.querySelectorAll('section').forEach(s => s.classList.remove('active')); document.getElementById(id).classList.add('active'); }} function toggleCustomFields() {{ document.getElementById('custom-fields').style.display = (document.getElementById('ai_provider').value === 'auto') ? 'none' : 'block'; }} function setBridgePreset(type) {{ const t = document.getElementById('bridge_lines'); const tog = document.getElementById('use_bridges'); if(type==='none') {{ t.value=''; tog.checked=false; }} else if(type==='obfs4') {{ t.value='Bridge obfs4 192.95.36.142:443 CDF7... cert=... iat-mode=0'; tog.checked=true; }} else if(type==='meek_lite') {{ t.value='Bridge meek_lite 0.0.2.0:1 url=https://meek.bamsoftware.com/ front=www.google.com'; tog.checked=true; }} else if(type==='snowflake') {{ t.value='Bridge snowflake 192.0.2.3:80'; tog.checked=true; }} }} function saveSettings() {{ document.title = 'CMD:save_settings:' + JSON.stringify({{ theme: document.getElementById('theme').value, accent: document.getElementById('accent').value, wallpaper: document.getElementById('wallpaper').value, search_engine: document.getElementById('search_engine').value, custom_search_url: document.getElementById('custom_search_url').value, gpu_acceleration: document.getElementById('gpu_acceleration').checked, ai_provider: document.getElementById('ai_provider').value, ai_api_url: document.getElementById('ai_api_url').value, ai_model: document.getElementById('ai_model').value, ai_api_key: document.getElementById('ai_api_key').value, proxy_enabled: document.getElementById('proxy_enabled').checked, use_bridges: document.getElementById('use_bridges').checked, bridge_lines: document.getElementById('bridge_lines').value, pause_history: document.getElementById('pause_history').checked, burn_animation: document.getElementById('burn_animation').value, clear_on_exit: document.getElementById('clear_on_exit').checked, adblock_enabled: document.getElementById('adblock_enabled').checked, cookies_enabled: document.getElementById('cookies_enabled').value, javascript_enabled: document.getElementById('javascript_enabled').checked }}); }} toggleCustomFields();</script></body></html>"""

def generate_history_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    return f"""<!DOCTYPE html><html><head><style>body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; padding: 40px; }} .item {{ background: {c['surface']}; padding: 16px; margin: 8px 0; border-radius: 8px; border: 1px solid {c['border']}; cursor: pointer; }} .item:hover {{ border-color: {c['accent']}; }} .item a {{ color: {c['accent']}; text-decoration: none; }}</style></head><body><h1>History</h1><div id="list"></div><script>const data = {json.dumps(settings_mgr.get("history", []))}; const list = document.getElementById('list'); if(data.length === 0) list.innerHTML = '<p>No history yet</p>'; else data.slice().reverse().forEach(item => {{ const div = document.createElement('div'); div.className = 'item'; div.innerHTML = `<strong>${{item.title}}</strong><a href="${{item.url}}">${{item.url}}</a>`; list.appendChild(div); }});</script></body></html>"""

def generate_downloads_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    downloads = main_window.downloads if hasattr(main_window, 'downloads') else []
    dl_list = "".join([f"<div class='item'><strong>{d['name']}</strong><p>{d['path']}</p></div>" for d in downloads]) if downloads else "<p>No active downloads.</p>"
    return f"""<!DOCTYPE html><html><head><style>body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; padding: 40px; }} .item {{ background: {c['surface']}; padding: 16px; margin: 8px 0; border-radius: 8px; border: 1px solid {c['border']}; }}</style></head><body><h1>Downloads</h1>{dl_list}</body></html>"""

def generate_adblock_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    
    allowlist_html = ""
    for d in sorted(blocklist_mgr.allowlist):
        allowlist_html += f"<div class='list-item'><span>{d}</span><button onclick=\"document.title='CMD:remove_allow:{d}'\">Remove</button></div>"
    if not allowlist_html: allowlist_html = "<p class='empty'>Allowlist is empty.</p>"
        
    log_html = ""
    for l in blocklist_mgr.get_log()[:100]:
        t = time.strftime('%H:%M:%S', time.localtime(l['time']))
        log_html += f"<tr><td>{t}</td><td><b>{html_lib.escape(l['domain'])}</b></td><td>{html_lib.escape(l['type'])}</td></tr>"
    if not log_html: log_html = "<tr><td colspan='3' class='empty'>No blocked requests logged in this session.</td></tr>"

    return f"""<!DOCTYPE html><html><head><style>
    body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; padding: 40px; }}
    h1 {{ color: {c['accent']}; margin-bottom: 20px; }}
    .card {{ background: {c['surface']}; padding: 24px; border-radius: 12px; border: 1px solid {c['border']}; margin-bottom: 24px; }}
    .list-item {{ display: flex; justify-content: space-between; padding: 8px 12px; background: {c['input_bg']}; border-radius: 6px; margin-bottom: 6px; }}
    .list-item button {{ background: #ff3b30; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; }}
    input {{ padding: 10px; border: 1px solid {c['border']}; border-radius: 6px; background: {c['input_bg']}; color: {c['text']}; width: 300px; margin-right: 10px; }}
    button.primary {{ padding: 10px 20px; background: {c['accent']}; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid {c['border']}; font-size: 14px; }}
    th {{ color: {c['text_secondary']}; }}
    .empty {{ color: {c['text_secondary']}; font-style: italic; }}
    .stats {{ font-size: 14px; color: {c['text_secondary']}; margin-bottom: 16px; }}
    </style></head><body>
    <h1>Ad Blocker Controls</h1>
    
    <div class="card">
        <h2>Statistics</h2>
        <p class="stats">Active Blocklist Size: <b>{len(blocklist_mgr.domains):,}</b> domains</p>
        <p class="stats">Allowlist Size: <b>{len(blocklist_mgr.allowlist):,}</b> domains</p>
        <button class="primary" onclick="document.title='CMD:update_blocklist:'">Force Update Blocklist</button>
    </div>

    <div class="card">
        <h2>Allowlist (Whitelist)</h2>
        <p class="stats">Domains here will bypass the ad blocker.</p>
        <div style="margin-bottom: 16px;">
            <input type="text" id="new_allow" placeholder="example.com">
            <button class="primary" onclick="addAllow()">Add Domain</button>
        </div>
        <div id="allow_list">{allowlist_html}</div>
    </div>

    <div class="card">
        <h2>Block Log (Session)</h2>
        <p class="stats">Recently blocked requests. <button onclick="document.title='CMD:clear_log:'" style="background:transparent; color:{c['accent']}; border:none; cursor:pointer; text-decoration:underline;">Clear Log</button></p>
        <table>
            <thead><tr><th>Time</th><th>Blocked Domain</th><th>Resource Type</th></tr></thead>
            <tbody id="log_table">{log_html}</tbody>
        </table>
    </div>

    <script>
    function addAllow() {{
        const d = document.getElementById('new_allow').value.trim();
        if(d) {{ document.title = 'CMD:add_allow:' + d; }}
    }}
    </script>
    </body></html>"""

# ==========================================
# 18. MAIN BROWSER WINDOW
# ==========================================
# Global list to keep private profiles alive and prevent corruption
private_profiles = []

class JosephBrowser(QMainWindow):
    def __init__(self, is_private=False):
        super().__init__()
        self.is_private = is_private
        self.setWindowTitle("Joseph Browser (Private)" if is_private else "Joseph Browser")
        self.resize(1280, 800)
        self.setMinimumSize(800, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.app = QApplication.instance()
        self.settings = settings_mgr
        self.drag_pos = QPoint()
        self.dragging = False
        self.tabs = []
        self.is_system_dark = False
        self.downloads = []
        
        if "history" not in self.settings.data: self.settings.set("history", [])
            
        if is_private:
            self.profile = QWebEngineProfile() # No parent to prevent premature deletion
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
            private_profiles.append(self.profile)
        else:
            self.profile = QWebEngineProfile.defaultProfile()
            if not self.profile.persistentStoragePath():
                self.profile.setPersistentStoragePath(os.path.join(settings_mgr.dir, "storage"))
                self.profile.setCachePath(os.path.join(settings_mgr.dir, "cache"))
            
        self.profile.setHttpUserAgent(BRANDED_UA)
        self.interceptor = PrivacyInterceptor()
        self.profile.setUrlRequestInterceptor(self.interceptor)
        
        self.init_ui()
        self.apply_theme()
        
        if self.settings.get("proxy_enabled") and not is_private:
            tor_manager.start(self.settings.get("use_bridges"), self.settings.get("bridge_lines"))
            self.tor_status_bar.show()
            self.port_checker = TorPortChecker()
            self.port_checker.tor_ready.connect(self.on_tor_ready)
            self.port_checker.tor_failed.connect(self.on_tor_failed)
            self.port_checker.start()
            
        if blocklist_mgr.needs_update():
            self.updater = BlocklistUpdater(blocklist_mgr)
            self.updater.update_finished.connect(self.on_blocklist_updated)
            self.updater.start()
            
        self.profile.downloadRequested.connect(self.handle_download)
        self.add_new_tab(QUrl("josephbrowser://home"))
        
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(lambda: self.current_tab().page().triggerAction(QWebEnginePage.WebAction.Copy) if self.current_tab() else None)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(lambda: self.current_tab().page().triggerAction(QWebEnginePage.WebAction.Paste) if self.current_tab() else None)
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(lambda: self.load_internal_page("josephbrowser://history", new_tab=True))
        QShortcut(QKeySequence("Ctrl+Del"), self).activated.connect(self.burn_site)
        QShortcut(QKeySequence("Ctrl+Shift+Del"), self).activated.connect(self.burn_session)
        QShortcut(QKeySequence("F12"), self).activated.connect(self.toggle_panic)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self).activated.connect(self.open_private_window)

    def on_blocklist_updated(self, success, msg):
        print(f"[Blocklist] {msg}")

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        row1 = QHBoxLayout()
        row1.setContentsMargins(12, 12, 0, 0)
        self.tab_bar = QTabBar()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.currentChanged.connect(self.switch_tab)
        row1.addWidget(self.tab_bar)
        
        self.btn_new_tab = create_icon_btn("add", 28)
        self.btn_new_tab.setToolTip("New Tab")
        self.btn_new_tab.clicked.connect(lambda: self.add_new_tab(QUrl("josephbrowser://home")))
        row1.addWidget(self.btn_new_tab)
        
        row1.addStretch()
        
        self.btn_home = create_icon_btn("home", 36)
        self.btn_home.clicked.connect(lambda: self.load_internal_page("josephbrowser://home", new_tab=True))
        row1.addWidget(self.btn_home)
        row1.addSpacing(16)
        
        for btn_name, action in [("minimize", self.showMinimized), ("maximize", lambda: self.showNormal() if self.isMaximized() else self.showMaximized()), ("close", self.close)]:
            btn = create_icon_btn(btn_name, 45)
            btn.clicked.connect(action)
            row1.addWidget(btn)
        main_layout.addLayout(row1)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(12, 8, 12, 12)
        nav_row.setSpacing(8)
        
        self.btn_back = create_icon_btn("back")
        self.btn_back.clicked.connect(lambda: self.current_tab().back() if self.current_tab() else None)
        self.btn_fwd = create_icon_btn("forward")
        self.btn_fwd.clicked.connect(lambda: self.current_tab().forward() if self.current_tab() else None)
        self.btn_refresh = create_icon_btn("refresh")
        self.btn_refresh.clicked.connect(lambda: self.current_tab().reload() if self.current_tab() else None)
        
        self.loading_indicator = SpinningLabel(icon_mgr.get_path("loading"))
        
        self.url_container = QFrame()
        self.url_container.setObjectName("urlContainer")
        url_layout = QHBoxLayout(self.url_container)
        url_layout.setContentsMargins(12, 0, 12, 0)
        url_layout.setSpacing(8)
        
        self.btn_security = QPushButton()
        self.btn_security.setFixedSize(24, 24)
        self.btn_security.clicked.connect(self.show_security_info)
        self.btn_security.setIconSize(QSize(18, 18))
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter address")
        self.url_bar.returnPressed.connect(self.navigate_to)
        
        url_layout.addWidget(self.btn_security)
        url_layout.addWidget(self.url_bar, 1)
        
        self.btn_ext = create_icon_btn("extension")
        self.ext_menu = QMenu()
        self.btn_ext.setMenu(self.ext_menu)
        self.update_ext_menu()
        
        self.btn_tools = create_icon_btn("tools")
        self.btn_tools.setCheckable(True)
        self.btn_tools.clicked.connect(self.toggle_tools_sidebar)
        
        self.btn_more = create_icon_btn("more")
        self.more_menu = QMenu()
        
        self.more_menu.addAction("New Window", self.open_new_window)
        self.more_menu.addAction("New Private Window (Ctrl+Shift+N)", self.open_private_window)
        self.more_menu.addSeparator()
        
        self.more_menu.addAction("History (Ctrl+H)", lambda: self.load_internal_page("josephbrowser://history", new_tab=True))
        self.more_menu.addAction("Downloads", lambda: self.load_internal_page("josephbrowser://downloads", new_tab=True))
        self.more_menu.addAction("Settings", lambda: self.load_internal_page("josephbrowser://settings", new_tab=True))
        self.more_menu.addSeparator()
        self.more_menu.addAction("Panic Mode (Hide Window) [F12]", self.toggle_panic)
        self.btn_more.setMenu(self.more_menu)
        
        nav_row.addWidget(self.btn_back)
        nav_row.addWidget(self.btn_fwd)
        nav_row.addWidget(self.btn_refresh)
        nav_row.addWidget(self.loading_indicator)
        nav_row.addWidget(self.url_container, 1)
        nav_row.addWidget(self.btn_ext)
        nav_row.addWidget(self.btn_tools)
        nav_row.addWidget(self.btn_more)
        main_layout.addLayout(nav_row)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tab_stack = QStackedWidget()
        self.tools_sidebar = ToolsSidebar(self)
        
        self.content_splitter.addWidget(self.tab_stack)
        self.content_splitter.addWidget(self.tools_sidebar)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 0)
        main_layout.addWidget(self.content_splitter, 1)

        self.tor_status_bar = TorStatusBar()
        main_layout.addWidget(self.tor_status_bar)
        
        self.tray_icon = QSystemTrayIcon(self)
        icon = icon_mgr.get_icon("home")
        if not icon:
            pm = QPixmap(32, 32)
            pm.fill(QColor(28, 75, 130))
            icon = QIcon(pm)
        self.tray_icon.setIcon(icon)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def open_private_window(self):
        private_win = JosephBrowser(is_private=True)
        private_win.show()
        
    def open_new_window(self):
        new_win = JosephBrowser(is_private=False)
        new_win.show()

    def toggle_panic(self):
        self.hide()
        if self.tray_icon.supportsMessages():
            self.tray_icon.showMessage("Joseph Browser", "Panic mode activated. Click the tray icon to restore.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def on_tor_ready(self):
        self.tor_status_bar.label.setText("✓ Tor Connected")
        self.tor_status_bar.progress.hide()
        QTimer.singleShot(3000, self.tor_status_bar.hide)

    def on_tor_failed(self):
        self.tor_status_bar.label.setText("✕ Tor Connection Failed")
        self.tor_status_bar.progress.hide()
        QTimer.singleShot(5000, self.tor_status_bar.hide)
        
    def show_security_info(self):
        tab = self.current_tab()
        if not tab: return
        scheme = tab.url().scheme()
        
        protections = [
            "• ECH (Encrypted Client Hello)",
            "• HTTPS-Only Mode Enforced",
            "• Tracker Request Blocking",
            "• Ad Container Removal",
            "• WebRTC leak prevention",
            "• Canvas/WebGL spoofing",
            "• Hardware Masking (Chromium Flags)"
        ]
        
        cookie_mode = self.settings.get("cookies_enabled")
        if cookie_mode == "all":
            protections.append("• Cookies: All Allowed")
        elif cookie_mode == "third-party":
            protections.append("• Cookies: Third-Party Blocked")
        else:
            protections.append("• Cookies: All Blocked")
            
        js_enabled = self.settings.get("javascript_enabled")
        protections.append(f"• JavaScript: {'Enabled' if js_enabled else 'Disabled'}")
        
        if self.settings.get("proxy_enabled"):
            protections.append("• Tor Network Routing (Remote DNS)")
        else:
            protections.append("• DNS-over-HTTPS (Cloudflare)")
            
        if scheme == "https":
            msg = f"✓ Encrypted connection to {tab.url().host()}\n\nActive protections:\n" + "\n".join(protections)
            QMessageBox.information(self, "Secure Connection", msg)
        else:
            msg = f"⚠ Connection is not encrypted.\n\nActive protections:\n" + "\n".join(protections)
            QMessageBox.warning(self, "Insecure Connection", msg)

    def update_ext_menu(self):
        self.ext_menu.clear()
        exts = self.settings.get("extensions")
        if not exts:
            self.ext_menu.addAction("No extensions installed").setEnabled(False)
        else:
            for ext_path in exts:
                manifest_path = Path(ext_path) / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f: manifest = json.load(f)
                        name = manifest.get("name", Path(ext_path).name)
                        action = self.ext_menu.addAction(name)
                        action.triggered.connect(lambda checked, p=ext_path: self.open_extension(p))
                    except: pass
        self.ext_menu.addSeparator()
        self.ext_menu.addAction("Manage Extensions", lambda: self.load_internal_page("josephbrowser://settings", new_tab=True))

    def open_extension(self, ext_path):
        manifest_path = Path(ext_path) / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path) as f: manifest = json.load(f)
                popup_html = manifest.get("action", {}).get("default_popup") or manifest.get("browser_action", {}).get("default_popup")
                if popup_html:
                    dialog = QDialog(self)
                    dialog.setWindowTitle(manifest.get("name", "Extension"))
                    dialog.resize(350, 400)
                    layout = QVBoxLayout(dialog)
                    view = QWebEngineView(dialog)
                    view.setUrl(QUrl.fromLocalFile(str(Path(ext_path) / popup_html)))
                    layout.addWidget(view)
                    dialog.exec()
                    return
            except: pass
        QMessageBox.information(self, "Extension", "No popup available.")

    def toggle_tools_sidebar(self, checked):
        self.tools_sidebar.setVisible(checked)

    def execute_command(self, cmd, args, tab):
        if cmd == "save_settings":
            if args:
                try:
                    new_settings = json.loads(args[0])
                    for k, v in new_settings.items(): self.settings.set(k, v)
                    self.apply_theme()
                    
                    if self.settings.get("proxy_enabled"):
                        tor_manager.start(self.settings.get("use_bridges"), self.settings.get("bridge_lines"))
                        self.tor_status_bar.show()
                        self.tor_status_bar.label.setText("Connecting to Tor...")
                        self.tor_status_bar.progress.show()
                        self.port_checker = TorPortChecker()
                        self.port_checker.tor_ready.connect(self.on_tor_ready)
                        self.port_checker.tor_failed.connect(self.on_tor_failed)
                        self.port_checker.start()
                    else:
                        tor_manager.stop()
                        
                    tab.page().setHtml(generate_settings_html(self), QUrl("josephbrowser://settings"))
                    QMessageBox.information(self, "Settings", "Settings saved. Restart browser to apply all changes.")
                except Exception as e: print(f"Error saving settings: {e}")
        elif cmd == "add_ext":
            path = QFileDialog.getExistingDirectory(self, "Select Extension Folder")
            if path:
                exts = self.settings.get("extensions")
                if path not in exts:
                    exts.append(path)
                    self.settings.set("extensions", exts)
                    self.update_ext_menu()
            tab.page().setHtml(generate_settings_html(self), QUrl("josephbrowser://settings"))
        elif cmd == "remove_ext":
            if args:
                path = args[0]
                exts = self.settings.get("extensions")
                if path in exts:
                    exts.remove(path)
                    self.settings.set("extensions", exts)
                    self.update_ext_menu()
            tab.page().setHtml(generate_settings_html(self), QUrl("josephbrowser://settings"))
        elif cmd == "burn_data":
            burn_type = args[0] if args else "session"
            if burn_type == "session":
                self.profile.clearHttpCache()
                self.profile.cookieStore().deleteAllCookies()
                self.settings.set("history", [])
                tor_manager.new_circuit()
                QMessageBox.information(self, "Session Burned", "All data cleared and Tor circuit renewed.")
                tab.setUrl(QUrl("josephbrowser://home"))
            else:
                tab.page().runJavaScript("try { window.localStorage.clear(); window.sessionStorage.clear(); document.cookie.split(';').forEach(c => { document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/'); }); } catch(e) {}")
                tab.reload()
        elif cmd == "fetch_bridges":
            bridges = tor_manager.fetch_moat_bridges()
            if bridges:
                self.settings.set("bridge_lines", bridges)
                QMessageBox.information(self, "Bridges Fetched", "New bridges have been added to your configuration.")
            else:
                QMessageBox.warning(self, "Moat Failed", "Could not fetch bridges automatically. Please add them manually.")
        elif cmd == "add_allow":
            if args:
                blocklist_mgr.add_to_allowlist(args[0])
                tab.page().setHtml(generate_adblock_html(self), QUrl("josephbrowser://adblock"))
        elif cmd == "remove_allow":
            if args:
                blocklist_mgr.remove_from_allowlist(args[0])
                tab.page().setHtml(generate_adblock_html(self), QUrl("josephbrowser://adblock"))
        elif cmd == "clear_log":
            blocklist_mgr.clear_log()
            tab.page().setHtml(generate_adblock_html(self), QUrl("josephbrowser://adblock"))
        elif cmd == "update_blocklist":
            self.updater = BlocklistUpdater(blocklist_mgr)
            self.updater.update_finished.connect(self.on_blocklist_updated)
            self.updater.start()
            QMessageBox.information(self, "Blocklist", "Updating blocklist in background...")

    def load_internal_page(self, url_str, new_tab=False):
        if new_tab:
            self.add_new_tab(QUrl(url_str))
        else:
            tab = self.current_tab()
            if not tab:
                self.add_new_tab(QUrl(url_str))
            else:
                if url_str == "josephbrowser://settings": tab.page().setHtml(generate_settings_html(self), QUrl(url_str))
                elif url_str == "josephbrowser://history": tab.page().setHtml(generate_history_html(self), QUrl(url_str))
                elif url_str == "josephbrowser://downloads": tab.page().setHtml(generate_downloads_html(self), QUrl(url_str))
                elif url_str == "josephbrowser://home": tab.page().setHtml(generate_home_html(self), QUrl(url_str))
                elif url_str == "josephbrowser://adblock": tab.page().setHtml(generate_adblock_html(self), QUrl(url_str))
                self.update_url_bar(tab, QUrl(url_str))

    def apply_theme(self):
        try:
            if hasattr(self.app.styleHints(), 'colorScheme'): 
                self.is_system_dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            else: 
                self.is_system_dark = self.app.palette().color(QPalette.ColorRole.Window).lightness() < 128
        except:
            self.is_system_dark = False

        accent = self.settings.get("accent")
        if self.is_private:
            accent = "#6c5ce7" if self.is_system_dark else "#a8a5e6"

        c = ThemeManager.get_colors(self.settings.get("theme"), accent, self.is_system_dark)
        wallpaper = self.settings.get("wallpaper")
        bg_style = f"background-color: {c['bg']};"
        if wallpaper:
            if wallpaper.startswith("http"): bg_style = f"background-image: url('{wallpaper}'); background-size: cover;"
            else: bg_style = f"background-image: url('file:///{wallpaper}'); background-size: cover;"

        close_icon = icon_mgr.get_path("close")
        close_qss = f"image: url('{close_icon}');" if close_icon else ""

        self.setStyleSheet(f"""
            QMainWindow {{ {bg_style} }} 
            QWidget {{ background: transparent; color: {c['text']}; }} 
            
            QTabBar::tab {{ background: {c['surface']}; color: {c['text_secondary']}; border: 1px solid {c['border']}; border-bottom: none; padding: 10px 20px; border-radius: 8px 8px 0 0; margin-right: 4px; }} 
            QTabBar::tab:selected {{ background: {c['bg']}; color: {c['text']}; border-bottom: 2px solid {c['accent']}; }} 
            QTabBar::close-button {{ {close_qss} subcontrol-position: right; padding: 4px; border-radius: 4px; }} 
            QTabBar::close-button:hover {{ background: rgba(255,0,0,0.2); }} 
            
            QPushButton {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }} 
            QPushButton:hover {{ background: {c['hover']}; }} 
            QPushButton::menu-indicator {{ image: none; width: 0px; }}
            
            #urlContainer {{ background: {c['input_bg']}; border: 1px solid {c['border']}; border-radius: 20px; }}
            #urlContainer QLineEdit {{ border: none; background: transparent; padding: 10px 8px; font-size: 14px; color: {c['text']}; }}
            #urlContainer QPushButton {{ border: none; background: transparent; border-radius: 0; padding: 0; }}
            
            QTextEdit {{ background: {c['input_bg']}; border: 1px solid {c['border']}; color: {c['text']}; border-radius: 8px; padding: 12px; }} 
            QComboBox {{ background: {c['input_bg']}; border: 1px solid {c['border']}; color: {c['text']}; border-radius: 6px; padding: 8px; }} 
            QMenu {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 8px 0; }} 
            QMenu::item {{ padding: 10px 24px; }} 
            QMenu::item:selected {{ background: {c['accent']}; color: white; }}
        """)

    def add_new_tab(self, url):
        tab = WebTab(self, self.profile)
        idx = self.tab_stack.addWidget(tab)
        self.tabs.append(tab)
        
        tab.titleChanged.connect(lambda t, tab_obj=tab: tab_obj.handle_title_change(t))
        tab.titleChanged.connect(lambda t, tab_obj=tab: self.update_tab_title(tab_obj, t))
        tab.urlChanged.connect(lambda u, tab_obj=tab: self.update_url_bar(tab_obj, u))
        tab.iconChanged.connect(lambda icon, tab_obj=tab: self.update_tab_icon(tab_obj, icon))
        tab.loadStarted.connect(self.loading_indicator.start)
        tab.loadFinished.connect(self.loading_indicator.stop)
        
        self.tab_bar.addTab("New Tab")
        self.tab_bar.setCurrentIndex(idx)
        
        url_str = url.toString()
        if url_str.startswith("josephbrowser://"):
            self.load_internal_page(url_str, new_tab=False)
        else:
            tab.setUrl(url)
            
        self.switch_tab(idx)
        return tab

    def update_tab_title(self, tab_obj, title):
        try:
            idx = self.tabs.index(tab_obj)
            if idx < self.tab_bar.count() and not title.startswith("CMD:"):
                self.tab_bar.setTabText(idx, title[:25] + "..." if len(title) > 25 else title)
                if not self.settings.get("pause_history") and tab_obj.url().scheme() not in ["josephbrowser", "about"]:
                    history = self.settings.get("history")
                    history.append({"title": title, "url": tab_obj.url().toString()})
                    if len(history) > 200: history = history[-200:]
                    self.settings.set("history", history)
        except: pass

    def update_tab_icon(self, tab_obj, icon):
        try:
            idx = self.tabs.index(tab_obj)
            if idx < self.tab_bar.count(): self.tab_bar.setTabIcon(idx, icon)
        except: pass

    def update_url_bar(self, tab_obj, url):
        if tab_obj == self.current_tab():
            url_str = url.toString()
            self.url_bar.blockSignals(True)
            self.url_bar.setText(url_str)
            self.url_bar.blockSignals(False)
            
            if url.scheme() == "https":
                icon = icon_mgr.get_icon("secure")
            else:
                icon = icon_mgr.get_icon("insecure")
                
            if icon:
                self.btn_security.setIcon(icon)
                self.btn_security.setText("")
            else:
                self.btn_security.setText("🔒" if url.scheme() == "https" else "⚠")

    def close_tab(self, index):
        if len(self.tabs) > 1:
            widget = self.tab_stack.widget(index)
            self.tab_stack.removeWidget(widget)
            widget.deleteLater()
            self.tabs.pop(index)
            self.tab_bar.removeTab(index)
        else:
            self.tabs[0].setUrl(QUrl("josephbrowser://home"))

    def switch_tab(self, index):
        if index < len(self.tabs):
            self.tab_stack.setCurrentIndex(index)
            self.update_url_bar(self.tabs[index], self.tabs[index].url())

    def current_tab(self):
        idx = self.tab_stack.currentIndex()
        return self.tab_stack.widget(idx) if idx != -1 else None

    def navigate_to(self):
        text = self.url_bar.text().strip().lower()
        if not text: return
        internal_map = {"settings": "josephbrowser://settings", "history": "josephbrowser://history", "downloads": "josephbrowser://downloads", "home": "josephbrowser://home", "newtab": "josephbrowser://home", "adblock": "josephbrowser://adblock"}
        if text in internal_map or text.startswith("josephbrowser://"):
            self.load_internal_page(text if text.startswith("josephbrowser://") else internal_map[text], new_tab=True)
            return
        text = self.url_bar.text().strip()
        if not text.startswith(("http://", "https://")):
            if "." in text and " " not in text: text = "https://" + text
            else: text = get_search_url().replace('%s', text)
        tab = self.current_tab()
        if tab: tab.setUrl(QUrl(text))

    def burn_site(self):
        tab = self.current_tab()
        if tab: tab.page().runJavaScript(get_burn_js(self.settings.get("burn_animation", "blackhole"), "site"))

    def burn_session(self):
        tab = self.current_tab()
        if tab: tab.page().runJavaScript(get_burn_js(self.settings.get("burn_animation", "blackhole"), "session"))

    def view_source(self):
        tab = self.current_tab()
        if tab:
            self.tools_sidebar.tabs.setCurrentIndex(2)
            self.tools_sidebar.show()
            self.btn_tools.setChecked(True)
            self.tools_sidebar.refresh_source()

    def handle_download(self, item):
        filename = item.suggestedFileName()
        if not filename:
            filename = "download"
            
        ext = Path(filename).suffix.lower()
        dangerous_exts = [".exe", ".msi", ".bat", ".sh", ".cmd", ".scr", ".pif"]
        if ext in dangerous_exts:
            reply = QMessageBox.warning(self, "Security Warning", 
                                        f"You are about to download an executable file:\n\n{filename}\n\nAre you sure you want to proceed?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                item.cancel()
                return
            
        download_dir = Path.home() / "Downloads"
        download_dir.mkdir(exist_ok=True)
        
        save_path = download_dir / filename
        if save_path.exists():
            base, ext = save_path.stem, save_path.suffix
            count = 1
            while save_path.exists():
                save_path = download_dir / f"{base} ({count}){ext}"
                count += 1

        item.setDownloadDirectory(str(download_dir))
        item.setDownloadFileName(save_path.name)
        item.accept()
        
        self.downloads.append({"name": save_path.name, "path": str(save_path)})

    def closeEvent(self, event):
        tor_manager.stop()
        if self.settings.get("clear_on_exit") and not self.is_private:
            self.profile.clearHttpCache()
            self.profile.cookieStore().deleteAllCookies()
            self.settings.set("history", [])
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
            if event.position().y() < 45: self.dragging = True

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and getattr(self, 'dragging', False):
            if event.position().y() < 100: 
                self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
                self.drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.dragging = False

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        browser = JosephBrowser()
        browser.show()
        sys.exit(app.exec())
    except Exception as e:
        exception_hook(type(e), e, e.__traceback__)