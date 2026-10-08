import sys
import os
import json
import requests
import traceback
import html as html_lib
import subprocess
import random
import socket
import time
from pathlib import Path
from urllib.parse import unquote

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
            "burn_animation": "blackhole", "clear_on_exit": False, "adblock_enabled": True
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
# 2. ICON MANAGER
# ==========================================
class IconManager:
    def __init__(self):
        self.cache = {}
        self.icon_dir = SCRIPT_DIR / "data" / "images"
        self.fallbacks = {
            "back": "◀", "forward": "▶", "close": "✕", "refresh": "⟳", "settings": "⚙", "more": "⋮", 
            "extension": "🧩", "code": "🤖", "info": "ⓘ", "secure": "🔒", "insecure": "⚠", "add": "+",
            "dark": "🌙", "light": "☀", "system": "💻", "warning": "⚠", "minimize": "—", "maximize": "❐", 
            "home": "⌂", "loading": "⟳", "tools": "🛠"
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
# 3. CHROMIUM HARDENING FLAGS
# ==========================================
flags = [
    "--disable-dev-shm-usage", "--disable-software-rasterizer",
    "--disable-features=CalculateNativeWinOcclusion,msaa-intrinsics",
    "--disable-breakpad", "--disable-client-side-phishing-detection",
    "--no-pings", "--disable-background-networking",
    "--enable-features=EncryptedClientHello,HttpsOnlyMode",
    "--block-third-party-cookies", "--blink-settings=hardwareConcurrency=8,deviceMemory=8"
]

if settings_mgr.get("proxy_enabled"):
    flags.append('--proxy-server="socks5://127.0.0.1:9050"')
    flags.append('--host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"')
else:
    flags.append("--enable-features=DnsOverHttps")
    flags.append("--dns-over-https=https://cloudflare-dns.com/dns-query")

if not settings_mgr.get("gpu_acceleration"): flags.append("--disable-gpu")
    
exts = settings_mgr.get("extensions")
if exts:
    abs_exts = [os.path.abspath(p).replace("\\", "\\\\") for p in exts if os.path.exists(p)]
    if abs_exts: flags.append("--load-extension=" + ",".join(abs_exts))
        
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)

# ==========================================
# 4. PYQT IMPORTS
# ==========================================
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabBar, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QWidget, QStackedWidget, QTextEdit,
                             QLabel, QMessageBox, QMenu, QFrame, QSplitter, QComboBox, QFileDialog, QDialog,
                             QTabWidget, QGridLayout, QProgressBar)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript, QWebEngineUrlRequestInterceptor
from PyQt6.QtCore import QUrl, Qt, QSize, pyqtSignal, QPoint, QThread, QTimer
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QColor, QAction, QPainter, QPen, QPixmap
from PyQt6.QtNetwork import QNetworkProxy

try:
    from PyQt6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

# ==========================================
# 5. GLOBAL ERROR HANDLER
# ==========================================
def exception_hook(exc_type, exc_value, exc_traceback):
    print("\n" + "="*60)
    print("JOSEPH BROWSER CRASHED")
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    print("="*60)
    input("Press Enter to close...")
sys.excepthook = exception_hook

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
# 7. INTEGRATED TOR MANAGER (LYREBIRD SUPPORT)
# ==========================================
class TorManager:
    def __init__(self):
        self.process = None
        self.tor_exe = SCRIPT_DIR / "tor" / "tor" / "tor.exe"
        self.torrc_path = Path(settings_mgr.dir) / "torrc"
        
    def find_executable(self, name):
        search_dirs = [
            self.tor_exe.parent, self.tor_exe.parent / "PluggableTransports", self.tor_exe.parent / "pluggable_transports",
            self.tor_exe.parent.parent, self.tor_exe.parent.parent / "PluggableTransports", self.tor_exe.parent.parent / "pluggable_transports"
        ]
        for d in search_dirs:
            if d.exists():
                for root, dirs, files in os.walk(d):
                    if name in files: return os.path.join(root, name)
        return None

    def write_torrc(self, use_bridges, bridge_lines):
        config = ["SOCKSPort 9050", "ControlPort 9051", "CookieAuthentication 0"]
        
        lyrebird_path = self.find_executable("lyrebird.exe")
        obfs4_path = self.find_executable("obfs4proxy.exe")
        snowflake_path = self.find_executable("snowflake-client.exe")
        meek_path = self.find_executable("meek-client.exe")
        
        available_transports = []
        
        if lyrebird_path:
            config.append(f'ClientTransportPlugin obfs4 exec "{lyrebird_path}"')
            config.append(f'ClientTransportPlugin meek_lite exec "{lyrebird_path}"')
            config.append(f'ClientTransportPlugin snowflake exec "{lyrebird_path}"')
            available_transports.extend(["obfs4", "meek_lite", "snowflake"])
            print(f"[Tor Manager] Using modern Lyrebird transport client: {lyrebird_path}")
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
                
                # Auto-convert meek to meek_lite if Lyrebird is used
                if "meek_lite" in available_transports and "meek" not in available_transports:
                    if "Bridge meek " in line: line = line.replace("Bridge meek ", "Bridge meek_lite ", 1)
                    elif line.startswith("meek "): line = "meek_lite " + line[5:]
                    elif " meek " in line: line = line.replace(" meek ", " meek_lite ", 1)
                
                # Relaxed parsing: accept direct bridges (IP:Port) and IPv6 formats
                parts = line.split()
                if len(parts) >= 2:
                    if not line.lower().startswith("bridge "):
                        line = f"Bridge {line}"
                    valid_bridges.append(line)
                    
            if valid_bridges:
                config.append("UseBridges 1")
                config.extend(valid_bridges)
            else:
                print("[Tor Manager] WARNING: No valid bridges configured.")
                    
        with open(self.torrc_path, "w", encoding="utf-8") as f:
            f.write("\n".join(config))
            
    def start(self, use_bridges, bridge_lines):
        self.stop()
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/IM', 'tor.exe'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
        
        if not self.tor_exe.exists():
            print(f"[Tor Manager] Executable not found at {self.tor_exe}")
            return
            
        self.write_torrc(use_bridges, bridge_lines)
        
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
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
BLOCKLIST = ["google-analytics.com", "googletagmanager.com", "doubleclick.net", "facebook.net", "connect.facebook.net", "analytics.twitter.com", "ads.twitter.com", "scorecardresearch.com", "taboola.com", "criteo.com", "adnxs.com"]

class PrivacyInterceptor(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        if not settings_mgr.get("adblock_enabled"):
            info.setHttpHeader(b"DNT", b"1")
            info.setHttpHeader(b"Sec-GPC", b"1")
            return

        url = info.requestUrl().toString().lower()
        for tracker in BLOCKLIST:
            if tracker in url:
                info.block(True)
                return
        info.setHttpHeader(b"DNT", b"1")
        info.setHttpHeader(b"Sec-GPC", b"1")

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
        if HAS_SVG and self.svg_path:
            self.renderer = QSvgRenderer(self.svg_path)
            if self.renderer.isValid(): self.use_svg = True

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
        return f"""(() => {{ const style = document.createElement('style'); style.innerHTML = `@keyframes joseph-suck {{ 0% {{ transform: scale(1) rotate(0deg); filter: blur(0); opacity: 1; }} 100% {{ transform: scale(0.01) rotate(1080deg); filter: blur(20px); opacity: 0; }} }} body {{ animation: joseph-suck 2s forwards ease-in !important; transform-origin: center center !important; overflow: hidden !important; }} #joseph-blackhole {{ position: fixed; top: 50%; left: 50%; width: 10px; height: 10px; background: black; border-radius: 50%; z-index: 999999; box-shadow: 0 0 50px 20px black; animation: joseph-bh-grow 2s forwards ease-in; transform: translate(-50%, -50%); }} @keyframes joseph-bh-grow {{ 0% {{ width: 10px; height: 10px; }} 100% {{ width: 200vmax; height: 200vmax; }} }}`; document.head.appendChild(style); const bh = document.createElement('div'); bh.id = 'joseph-blackhole'; document.body.appendChild(bh); setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000); }})();"""
    elif anim_type == "shredder":
        return f"""(() => {{ const style = document.createElement('style'); style.innerHTML = `@keyframes joseph-shred {{ 0% {{ transform: translateY(0) rotate(0); opacity: 1; }} 100% {{ transform: translateY(150vh) rotate(var(--rot)); opacity: 0; }} }}`; document.head.appendChild(style); const html = document.body.innerHTML; document.body.innerHTML = ''; document.body.style.margin = '0'; document.body.style.overflow = 'hidden'; for(let i=0; i<20; i++) {{ const strip = document.createElement('div'); const rot = (Math.random() - 0.5) * 60; strip.style.cssText = `position:absolute; top:${{i*5}}vh; left:0; width:100%; height:5vh; overflow:hidden; --rot: ${{rot}}deg; animation: joseph-shred 1.5s forwards ease-in ${{Math.random()*0.5}}s;`; strip.innerHTML = `<div style="position:absolute; top:-${{i*5}}vh; left:0; width:100%; height:100vh;">${{html}}</div>`; document.body.appendChild(strip); }} setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000); }})();"""
    elif anim_type == "incinerator":
        return f"""(() => {{ const style = document.createElement('style'); style.innerHTML = `@keyframes joseph-burn {{ 0% {{ filter: brightness(1); }} 20% {{ filter: brightness(1.5) sepia(1) hue-rotate(-30deg); }} 100% {{ filter: brightness(0) blur(10px); opacity: 0; }} }} body {{ animation: joseph-burn 2s forwards ease-in !important; overflow: hidden !important; }}`; document.head.appendChild(style); setTimeout(() => {{ document.title = 'CMD:burn_data:{burn_type}'; }}, 2000); }})();"""
    elif anim_type == "explode":
        return f"""(() => {{
            const style = document.createElement('style');
            style.innerHTML = `
                @keyframes joseph-explode {{
                    0% {{ transform: translate(0, 0) rotate(0deg) scale(1); opacity: 1; }}
                    100% {{ transform: translate(var(--tx), var(--ty)) rotate(var(--rot)) scale(0.2); opacity: 0; }}
                }}
            `;
            document.head.appendChild(style);
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
# 14. INTERNAL PAGES
# ==========================================
def generate_home_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    search_url = get_search_url()
    return f"""<!DOCTYPE html><html><head><style>body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; margin: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; }} .logo {{ font-size: 64px; font-weight: 700; color: {c['accent']}; margin-bottom: 40px; }} .search-box input {{ width: 600px; padding: 16px 24px; font-size: 18px; border: 2px solid {c['border']}; border-radius: 50px; background: {c['surface']}; color: {c['text']}; }} .shortcuts {{ display: flex; gap: 16px; margin-top: 40px; }} .shortcut {{ padding: 12px 24px; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; text-decoration: none; color: {c['text']}; }}</style></head><body><div class="logo">Joseph</div><form class="search-box" onsubmit="window.location.href='{search_url}'.replace('%s', encodeURIComponent(document.getElementById('search').value)); return false;"><input type="text" id="search" placeholder="Search the web..." autofocus></form><div class="shortcuts"><a href="https://duckduckgo.com" class="shortcut">DuckDuckGo</a><a href="josephbrowser://settings" class="shortcut">Settings</a></div></body></html>"""

def generate_settings_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    exts = settings_mgr.get("extensions")
    ext_list = "".join([f"<div class='ext-item'><span>{Path(ext).name}</span><button onclick=\"removeExt('{ext}')\">Remove</button></div>" for ext in exts]) if exts else "<p class='empty'>No extensions installed</p>"
    search_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("search_engine")==k else ""}>{k.title()}</option>' for k in SEARCH_ENGINES.keys()])
    provider_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("ai_provider")==k else ""}>{v}</option>' for k, v in AI_PROVIDERS.items()])
    anim_options = "".join([f'<option value="{k}" {"selected" if settings_mgr.get("burn_animation")==k else ""}>{k.title()}</option>' for k in ["blackhole", "incinerator", "shredder", "explode"]])
    
    checks = {k: "checked" if settings_mgr.get(k) else "" for k in ["proxy_enabled", "use_bridges", "gpu_acceleration", "pause_history", "clear_on_exit", "adblock_enabled"]}

    return f"""<!DOCTYPE html><html><head><style>* {{ box-sizing: border-box; margin: 0; padding: 0; }} body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; display: flex; height: 100vh; }} .sidebar {{ width: 250px; background: {c['surface']}; border-right: 1px solid {c['border']}; padding: 20px 0; }} .nav-btn {{ display: block; width: 100%; text-align: left; padding: 12px 24px; background: transparent; border: none; color: {c['text_secondary']}; font-size: 15px; cursor: pointer; }} .nav-btn.active {{ background: {c['accent']}; color: white; border-left: 4px solid {c['accent']}; }} main {{ flex: 1; padding: 40px; overflow-y: auto; }} h1 {{ font-size: 28px; margin-bottom: 32px; }} h2 {{ font-size: 20px; margin-bottom: 24px; color: {c['accent']}; border-bottom: 1px solid {c['border']}; padding-bottom: 12px; }} .card {{ background: {c['surface']}; padding: 24px; border-radius: 12px; border: 1px solid {c['border']}; margin-bottom: 24px; }} label {{ display: block; margin-bottom: 8px; font-weight: 500; color: {c['text_secondary']}; }} input, select, textarea {{ width: 100%; padding: 12px 16px; border: 1px solid {c['border']}; border-radius: 8px; background: {c['input_bg']}; color: {c['text']}; margin-bottom: 16px; }} .checkbox-row {{ display: flex; align-items: center; margin-bottom: 16px; }} button.primary {{ padding: 12px 24px; background: {c['accent']}; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }} .ext-item {{ display: flex; justify-content: space-between; align-items: center; padding: 12px; background: {c['input_bg']}; border-radius: 8px; margin-bottom: 8px; }} .ext-item button {{ padding: 6px 12px; background: #ff3b30; color: white; border: none; border-radius: 4px; cursor: pointer; }} .hint {{ color: {c['text_secondary']}; font-size: 13px; margin-top: 8px; }} section {{ display: none; }} section.active {{ display: block; }} .toggle {{ position: relative; display: inline-block; width: 46px; height: 24px; }} .toggle input {{ opacity: 0; width: 0; height: 0; }} .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: {c['border']}; transition: .4s; border-radius: 24px; }} .slider:before {{ position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }} input:checked + .slider {{ background-color: {c['accent']}; }} input:checked + .slider:before {{ transform: translateX(22px); }}</style></head><body><nav class="sidebar"><button class="nav-btn active" onclick="switchSection('general')">General</button><button class="nav-btn" onclick="switchSection('appearance')">Appearance</button><button class="nav-btn" onclick="switchSection('search')">Search</button><button class="nav-btn" onclick="switchSection('privacy')">Privacy & Tor</button><button class="nav-btn" onclick="switchSection('ai')">AI Assistant</button><button class="nav-btn" onclick="switchSection('extensions')">Extensions</button><button class="nav-btn" onclick="switchSection('optimizations')">Optimizations</button><button class="nav-btn" onclick="switchSection('about')">About</button></nav><main><h1>Settings</h1><section id="general" class="active"><h2>General</h2><div class="card"><p>Joseph Browser v{BROWSER_VERSION}</p><div class="checkbox-row" style="margin-top:16px;"><label class="toggle"><input type="checkbox" id="pause_history" {checks['pause_history']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Pause History</label></div><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="clear_on_exit" {checks['clear_on_exit']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Clear Data on Exit</label></div><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="adblock_enabled" {checks['adblock_enabled']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Enable Ad/Tracker Blocker</label></div><label>Shredding Animation</label><select id="burn_animation">{anim_options}</select></div></section><section id="appearance"><h2>Appearance</h2><div class="card"><label>Theme</label><select id="theme"><option value="system" {'selected' if settings_mgr.get('theme')=='system' else ''}>System</option><option value="light" {'selected' if settings_mgr.get('theme')=='light' else ''}>Light</option><option value="dark" {'selected' if settings_mgr.get('theme')=='dark' else ''}>Dark</option></select><label>Accent Color</label><input type="color" id="accent" value="{settings_mgr.get('accent')}"><label>Wallpaper URL</label><input type="text" id="wallpaper" value="{settings_mgr.get('wallpaper')}"></div></section><section id="search"><h2>Search</h2><div class="card"><label>Engine</label><select id="search_engine">{search_options}</select><label>Custom URL (%s)</label><input type="text" id="custom_search_url" value="{settings_mgr.get('custom_search_url')}"></div></section><section id="privacy"><h2>Privacy & Tor</h2><div class="card"><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="proxy_enabled" {checks['proxy_enabled']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Enable Tor</label></div><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="use_bridges" {checks['use_bridges']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">Use Bridges</label></div><label>Bridge Presets</label><select id="bridge_preset" onchange="setBridgePreset(this.value)"><option value="none">None</option><option value="obfs4">obfs4</option><option value="meek_lite">meek_lite</option><option value="snowflake">snowflake</option></select><label>Bridge Lines</label><textarea id="bridge_lines" rows="4" style="font-family:monospace;">{settings_mgr.get('bridge_lines')}</textarea><div class="hint" style="background:rgba(255,149,0,0.1); padding:12px; border-radius:8px; margin-top:16px;"><b>⚠️ Note:</b> Modern Tor uses <code>lyrebird.exe</code> in <code>pluggable_transports/</code> to handle obfs4, meek_lite, and snowflake. Direct IP bridges are also supported.</div></div></section><section id="ai"><h2>AI</h2><div class="card"><label>Provider</label><select id="ai_provider" onchange="toggleCustomFields()">{provider_options}</select><div id="custom-fields"><label>API URL</label><input type="text" id="ai_api_url" value="{settings_mgr.get('ai_api_url')}"><label>Model</label><input type="text" id="ai_model" value="{settings_mgr.get('ai_model')}"><label>API Key</label><input type="password" id="ai_api_key" value="{settings_mgr.get('ai_api_key')}"></div></div></section><section id="extensions"><h2>Extensions</h2><div class="card"><div id="ext-list">{ext_list}</div><button class="primary" onclick="addExt()" style="margin-top:16px;">+ Add Extension</button></div></section><section id="optimizations"><h2>Optimizations</h2><div class="card"><div class="checkbox-row"><label class="toggle"><input type="checkbox" id="gpu_acceleration" {checks['gpu_acceleration']}><span class="slider"></span></label><label style="margin-left:12px; cursor:pointer;">GPU Acceleration</label></div></div></section><section id="about"><h2>About</h2><div class="card"><p style="font-size:24px; font-weight:700; color:{c['accent']};">Joseph Browser</p><p>Version: {BROWSER_VERSION}</p><p class="hint" style="margin-top:12px;"><b>Hotkeys:</b><br>Ctrl+Del: Shred site data.<br>Ctrl+Shift+Del: Burn session & new Tor IP.</p></div></section><button class="primary" onclick="saveSettings()" style="position:fixed; bottom:40px; right:40px; padding:16px 32px; box-shadow:0 4px 12px rgba(0,0,0,0.2);">Save Settings</button></main><script>function switchSection(id) {{ document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active')); document.querySelector(`[onclick="switchSection('${{id}}')"]`).classList.add('active'); document.querySelectorAll('section').forEach(s => s.classList.remove('active')); document.getElementById(id).classList.add('active'); }} function toggleCustomFields() {{ document.getElementById('custom-fields').style.display = (document.getElementById('ai_provider').value === 'auto') ? 'none' : 'block'; }} function setBridgePreset(type) {{ const t = document.getElementById('bridge_lines'); const tog = document.getElementById('use_bridges'); if(type==='none') {{ t.value=''; tog.checked=false; }} else if(type==='obfs4') {{ t.value='Bridge obfs4 192.95.36.142:443 CDF7... cert=... iat-mode=0'; tog.checked=true; }} else if(type==='meek_lite') {{ t.value='Bridge meek_lite 0.0.2.0:1 url=https://meek.bamsoftware.com/ front=www.google.com'; tog.checked=true; }} else if(type==='snowflake') {{ t.value='Bridge snowflake 192.0.2.3:80'; tog.checked=true; }} }} function saveSettings() {{ document.title = 'CMD:save_settings:' + JSON.stringify({{ theme: document.getElementById('theme').value, accent: document.getElementById('accent').value, wallpaper: document.getElementById('wallpaper').value, search_engine: document.getElementById('search_engine').value, custom_search_url: document.getElementById('custom_search_url').value, gpu_acceleration: document.getElementById('gpu_acceleration').checked, ai_provider: document.getElementById('ai_provider').value, ai_api_url: document.getElementById('ai_api_url').value, ai_model: document.getElementById('ai_model').value, ai_api_key: document.getElementById('ai_api_key').value, proxy_enabled: document.getElementById('proxy_enabled').checked, use_bridges: document.getElementById('use_bridges').checked, bridge_lines: document.getElementById('bridge_lines').value, pause_history: document.getElementById('pause_history').checked, burn_animation: document.getElementById('burn_animation').value, clear_on_exit: document.getElementById('clear_on_exit').checked, adblock_enabled: document.getElementById('adblock_enabled').checked }}); }} function addExt() {{ document.title = 'CMD:add_ext:'; }} function removeExt(path) {{ document.title = 'CMD:remove_ext:' + path; }} toggleCustomFields();</script></body></html>"""

def generate_history_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    return f"""<!DOCTYPE html><html><head><style>body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; padding: 40px; }} .item {{ background: {c['surface']}; padding: 16px; margin: 8px 0; border-radius: 8px; border: 1px solid {c['border']}; cursor: pointer; }} .item:hover {{ border-color: {c['accent']}; }} .item a {{ color: {c['accent']}; text-decoration: none; }}</style></head><body><h1>History</h1><div id="list"></div><script>const data = {json.dumps(settings_mgr.get("history", []))}; const list = document.getElementById('list'); if(data.length === 0) list.innerHTML = '<p>No history yet</p>'; else data.slice().reverse().forEach(item => {{ const div = document.createElement('div'); div.className = 'item'; div.innerHTML = `<strong>${{item.title}}</strong><a href="${{item.url}}">${{item.url}}</a>`; list.appendChild(div); }});</script></body></html>"""

def generate_downloads_html(main_window):
    c = ThemeManager.get_colors(settings_mgr.get("theme"), settings_mgr.get("accent"), main_window.is_system_dark)
    return f"""<!DOCTYPE html><html><head><style>body {{ font-family: -apple-system, sans-serif; background: {c['bg']}; color: {c['text']}; padding: 40px; }}</style></head><body><h1>Downloads</h1><p>No active downloads.</p></body></html>"""

# ==========================================
# 15. WEB TAB & STEALTH (With New Tab Window Support)
# ==========================================
class WebPage(QWebEnginePage):
    def __init__(self, profile, parent, main_window):
        super().__init__(profile, parent)
        self.main_window = main_window

    def createWindow(self, type):
        # Intercept target="_blank" and middle-clicks to open in new tab
        new_tab = self.main_window.add_new_tab(QUrl("about:blank"))
        return new_tab.page()

class WebTab(QWebEngineView):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setPage(WebPage(QWebEngineProfile.defaultProfile(), self, main_window))
        self.titleChanged.connect(self.handle_title_change)
        
        settings = self.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        
        script = QWebEngineScript()
        script.setSourceCode("""(() => { Object.defineProperty(navigator, 'webdriver', {get: () => undefined}); Object.defineProperty(navigator, 'getBattery', {value: () => Promise.resolve({charging: true, level: 1})}); Object.defineProperty(screen, 'width', {get: () => 1920}); Object.defineProperty(screen, 'height', {get: () => 1080}); window.RTCPeerConnection = undefined; })();""")
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        try: script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        except: script.setWorldId(0)
        self.page().profile().scripts().insert(script)

    def handle_title_change(self, title):
        if title.startswith("CMD:"):
            parts = title.split(":", 2)
            if len(parts) >= 2:
                cmd = parts[1]
                args = [unquote(parts[2])] if len(parts) > 2 else []
                self.main_window.execute_command(cmd, args, self)
            self.page().runJavaScript("document.title = 'Joseph Browser';")

# ==========================================
# 16. AI SIDEBAR
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
# 17. TOOLS SIDEBAR (Calculator, AI, Source)
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
# 18. HELPER FUNCTIONS
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

# ==========================================
# 19. MAIN BROWSER WINDOW
# ==========================================
class JosephBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Joseph Browser")
        self.resize(1280, 800)
        self.setMinimumSize(800, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.app = QApplication.instance()
        self.settings = settings_mgr
        self.drag_pos = QPoint()
        self.dragging = False
        self.resize_edges = (False, False, False, False)
        self.tabs = []
        self.is_system_dark = False
        
        if "history" not in self.settings.data: self.settings.set("history", [])
            
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.interceptor = PrivacyInterceptor()
        profile.setUrlRequestInterceptor(self.interceptor)
        
        self.init_ui()
        self.apply_theme()
        
        if self.settings.get("proxy_enabled"):
            tor_manager.start(self.settings.get("use_bridges"), self.settings.get("bridge_lines"))
            self.tor_status_bar.show()
            self.port_checker = TorPortChecker()
            self.port_checker.tor_ready.connect(self.on_tor_ready)
            self.port_checker.tor_failed.connect(self.on_tor_failed)
            self.port_checker.start()
            
        QWebEngineProfile.defaultProfile().downloadRequested.connect(lambda item: item.accept())
        self.add_new_tab(QUrl("josephbrowser://home"))
        
        QShortcut(QKeySequence("Ctrl+U"), self).activated.connect(self.view_source)
        QShortcut(QKeySequence("Ctrl+Del"), self).activated.connect(self.burn_site)
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self).activated.connect(self.burn_session)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Row 1: Tabs & Window Controls
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
        self.btn_new_tab.clicked.connect(lambda: self.add_new_tab(QUrl("josephbrowser://home")))
        row1.addWidget(self.btn_new_tab)
        row1.addStretch()
        
        for btn_name, action in [("minimize", self.showMinimized), ("maximize", lambda: self.showNormal() if self.isMaximized() else self.showMaximized()), ("close", self.close)]:
            btn = create_icon_btn(btn_name, 45)
            btn.clicked.connect(action)
            row1.addWidget(btn)
        main_layout.addLayout(row1)

        # Row 2: Navigation
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
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter URL")
        self.url_bar.returnPressed.connect(self.navigate_to)
        
        self.btn_ext = create_icon_btn("extension")
        self.ext_menu = QMenu()
        self.btn_ext.setMenu(self.ext_menu)
        self.update_ext_menu()
        
        self.btn_tools = create_icon_btn("tools")
        self.btn_tools.setCheckable(True)
        self.btn_tools.clicked.connect(self.toggle_tools_sidebar)
        
        self.btn_more = create_icon_btn("more")
        self.more_menu = QMenu()
        self.more_menu.addAction("History", lambda: self.load_internal_page("josephbrowser://history"))
        self.more_menu.addAction("Downloads", lambda: self.load_internal_page("josephbrowser://downloads"))
        self.more_menu.addAction("Settings", lambda: self.load_internal_page("josephbrowser://settings"))
        self.more_menu.addSeparator()
        self.adblock_action = self.more_menu.addAction("Ad Blocker", self.toggle_adblock)
        self.adblock_action.setCheckable(True)
        self.adblock_action.setChecked(self.settings.get("adblock_enabled"))
        self.btn_more.setMenu(self.more_menu)
        
        nav_row.addWidget(self.btn_back)
        nav_row.addWidget(self.btn_fwd)
        nav_row.addWidget(self.btn_refresh)
        nav_row.addWidget(self.loading_indicator)
        nav_row.addWidget(self.url_bar, 1)
        nav_row.addWidget(self.btn_ext)
        nav_row.addWidget(self.btn_tools)
        nav_row.addWidget(self.btn_more)
        main_layout.addLayout(nav_row)

        # Content Area
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tab_stack = QStackedWidget()
        self.tools_sidebar = ToolsSidebar(self)
        
        self.content_splitter.addWidget(self.tab_stack)
        self.content_splitter.addWidget(self.tools_sidebar)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 0)
        main_layout.addWidget(self.content_splitter, 1)

        # Tor Status Bar
        self.tor_status_bar = TorStatusBar()
        main_layout.addWidget(self.tor_status_bar)

    def on_tor_ready(self):
        self.tor_status_bar.label.setText("✓ Tor Connected")
        self.tor_status_bar.progress.hide()
        QTimer.singleShot(3000, self.tor_status_bar.hide)

    def on_tor_failed(self):
        self.tor_status_bar.label.setText("✕ Tor Connection Failed")
        self.tor_status_bar.progress.hide()
        QTimer.singleShot(5000, self.tor_status_bar.hide)

    def toggle_adblock(self):
        state = self.adblock_action.isChecked()
        self.settings.set("adblock_enabled", state)
        QMessageBox.information(self, "Ad Blocker", f"Ad Blocker {'Enabled' if state else 'Disabled'}. Refresh pages to apply.")

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
        self.ext_menu.addAction("Manage Extensions", lambda: self.load_internal_page("josephbrowser://settings"))

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
                    self.adblock_action.setChecked(self.settings.get("adblock_enabled"))
                    
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
                    QMessageBox.information(self, "Settings", "Settings saved. Proxy changes require restart.")
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
                profile = QWebEngineProfile.defaultProfile()
                profile.clearHttpCache()
                profile.cookieStore().deleteAllCookies()
                self.settings.set("history", [])
                tor_manager.new_circuit()
                QMessageBox.information(self, "Session Burned", "All data cleared and Tor circuit renewed.")
                tab.setUrl(QUrl("josephbrowser://home"))
            else:
                tab.page().runJavaScript("try { window.localStorage.clear(); window.sessionStorage.clear(); document.cookie.split(';').forEach(c => { document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/'); }); } catch(e) {}")
                tab.reload()

    def load_internal_page(self, url_str):
        tab = self.current_tab()
        if not tab: return
        if url_str == "josephbrowser://settings": tab.page().setHtml(generate_settings_html(self), QUrl(url_str))
        elif url_str == "josephbrowser://history": tab.page().setHtml(generate_history_html(self), QUrl(url_str))
        elif url_str == "josephbrowser://downloads": tab.page().setHtml(generate_downloads_html(self), QUrl(url_str))
        elif url_str == "josephbrowser://home": tab.page().setHtml(generate_home_html(self), QUrl(url_str))
        else: tab.page().setHtml("<h1>404 Page Not Found</h1>", QUrl(url_str))

    def apply_theme(self):
        if hasattr(self.app.styleHints(), 'colorScheme'): self.is_system_dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        else: self.is_system_dark = self.app.palette().color(QPalette.ColorRole.Window).lightness() < 128

        c = ThemeManager.get_colors(self.settings.get("theme"), self.settings.get("accent"), self.is_system_dark)
        wallpaper = self.settings.get("wallpaper")
        bg_style = f"background-color: {c['bg']};"
        if wallpaper:
            if wallpaper.startswith("http"): bg_style = f"background-image: url('{wallpaper}'); background-size: cover;"
            else: bg_style = f"background-image: url('file:///{wallpaper}'); background-size: cover;"

        close_icon = icon_mgr.get_path("close")
        close_qss = f"image: url('{close_icon}');" if close_icon else ""

        self.setStyleSheet(f"""QMainWindow {{ {bg_style} }} QWidget {{ background: transparent; color: {c['text']}; }} QTabBar::tab {{ background: {c['surface']}; color: {c['text_secondary']}; border: 1px solid {c['border']}; border-bottom: none; padding: 10px 20px; border-radius: 8px 8px 0 0; margin-right: 4px; }} QTabBar::tab:selected {{ background: {c['bg']}; color: {c['text']}; border-bottom: 2px solid {c['accent']}; }} QTabBar::close-button {{ {close_qss} subcontrol-position: right; padding: 4px; border-radius: 4px; }} QTabBar::close-button:hover {{ background: rgba(255,0,0,0.2); }} QPushButton {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 6px; }} QPushButton:hover {{ background: {c['hover']}; }} QLineEdit {{ background: {c['input_bg']}; border: 1px solid {c['border']}; color: {c['text']}; padding: 10px 16px; border-radius: 20px; font-size: 14px; }} QTextEdit {{ background: {c['input_bg']}; border: 1px solid {c['border']}; color: {c['text']}; border-radius: 8px; padding: 12px; }} QComboBox {{ background: {c['input_bg']}; border: 1px solid {c['border']}; color: {c['text']}; border-radius: 6px; padding: 8px; }} QMenu {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 8px 0; }} QMenu::item {{ padding: 10px 24px; }} QMenu::item:selected {{ background: {c['accent']}; color: white; }}""")

    def add_new_tab(self, url):
        tab = WebTab(self)
        idx = self.tab_stack.addWidget(tab)
        self.tabs.append(tab)
        
        tab.titleChanged.connect(lambda t, tab_obj=tab: self.update_tab_title(tab_obj, t))
        tab.urlChanged.connect(lambda u, tab_obj=tab: self.update_url_bar(tab_obj, u))
        tab.iconChanged.connect(lambda icon, tab_obj=tab: self.update_tab_icon(tab_obj, icon))
        tab.loadStarted.connect(self.loading_indicator.start)
        tab.loadFinished.connect(self.loading_indicator.stop)
        
        self.tab_bar.addTab("New Tab")
        self.tab_bar.setCurrentIndex(idx)
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
            if "josephbrowser://" not in url_str: self.url_bar.setText(url_str)

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
        internal_map = {"settings": "josephbrowser://settings", "history": "josephbrowser://history", "downloads": "josephbrowser://downloads", "home": "josephbrowser://home", "newtab": "josephbrowser://home"}
        if text in internal_map or text.startswith("josephbrowser://"):
            self.load_internal_page(text if text.startswith("josephbrowser://") else internal_map[text])
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

    def closeEvent(self, event):
        tor_manager.stop()
        if self.settings.get("clear_on_exit"):
            profile = QWebEngineProfile.defaultProfile()
            profile.clearHttpCache()
            profile.cookieStore().deleteAllCookies()
            self.settings.set("history", [])
        super().closeEvent(event)

    EDGE_MARGIN = 8
    def get_edges(self, pos):
        rect = self.rect()
        return pos.x() < self.EDGE_MARGIN, pos.x() > rect.width() - self.EDGE_MARGIN, pos.y() < self.EDGE_MARGIN, pos.y() > rect.height() - self.EDGE_MARGIN

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
            if event.position().y() < 45: self.dragging = True
            self.resize_edges = self.get_edges(event.position().toPoint())
            if any(self.resize_edges): self.dragging = False

    def mouseMoveEvent(self, event):
        if not self.isMaximized():
            pos = event.position().toPoint()
            edges = self.get_edges(pos)
            if (edges[0] and edges[2]) or (edges[1] and edges[3]): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edges[1] and edges[2]) or (edges[0] and edges[3]): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edges[0] or edges[1]: self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edges[2] or edges[3]: self.setCursor(Qt.CursorShape.SizeVerCursor)
            else: self.setCursor(Qt.CursorShape.ArrowCursor)

        if event.buttons() == Qt.MouseButton.LeftButton:
            if any(getattr(self, 'resize_edges', (False, False, False, False))):
                delta = event.globalPosition().toPoint() - self.drag_pos
                geo = self.geometry()
                left, right, top, bottom = self.resize_edges
                min_w, min_h = 400, 300
                if left: 
                    new_left = geo.left() + delta.x()
                    if geo.width() + (geo.left() - new_left) >= min_w: geo.setLeft(new_left)
                if right: geo.setWidth(geo.width() + delta.x())
                if top: 
                    new_top = geo.top() + delta.y()
                    if geo.height() + (geo.top() - new_top) >= min_h: geo.setTop(new_top)
                if bottom: geo.setHeight(geo.height() + delta.y())
                self.setGeometry(geo)
                self.drag_pos = event.globalPosition().toPoint()
            elif getattr(self, 'dragging', False):
                if event.position().y() < 100: 
                    self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
                    self.drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resize_edges = (False, False, False, False)

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        browser = JosephBrowser()
        browser.show()
        sys.exit(app.exec())
    except Exception as e:
        exception_hook(type(e), e, e.__traceback__)
