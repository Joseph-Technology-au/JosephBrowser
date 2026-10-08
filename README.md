# JosephBrowser
Joseph Browser - The private, fast (not really), and secure web browser made with Python. 
Hopefully functional support for Windows, macOS, and Linux. 

# Setup
Method 1 (install dependencies)
    1. Install modern Python version
    2. Install dependencies below:
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
    3. Run browser.py
Method 2 (PyInstaller)
    1. Install PyInstaller with Python
    2. Run 'pyinstaller browser.py' 
    3. Run the executable file in dist/