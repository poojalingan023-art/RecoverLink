"""RecoverLink local launcher. Run: python start_recoverlink.py"""
from pathlib import Path
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
APP = ROOT / "app.py"
URL = "http://127.0.0.1:5000"


def open_browser():
    time.sleep(2.5)
    webbrowser.open(URL)


def main():
    print("=" * 58)
    print("RecoverLink - Local Demo Launcher")
    print("=" * 58)
    if not APP.exists() or not REQUIREMENTS.exists():
        print("Please run this launcher from the extracted RecoverLink project folder.")
        input("Press Enter to close...")
        return

    # Check imports first; don't require an internet connection if packages already exist.
    check = subprocess.run(
        [sys.executable, "-c", "import flask, flask_sqlalchemy, flask_login, flask_wtf, dotenv, werkzeug"],
        cwd=ROOT,
    )
    if check.returncode != 0:
        print("Required packages are missing; attempting installation...")
        install = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)], cwd=ROOT
        )
        if install.returncode != 0:
            print("\nPackage installation failed. Check your internet connection, then run:")
            print("python -m pip install -r requirements.txt")
            input("Press Enter to close...")
            return

    # Seed only when there is no database. Never reset an existing demo database here.
    database = ROOT / "instance" / "recoverlink.db"
    if not database.exists():
        print("Preparing demo data because no local database exists yet...")
        seeded = subprocess.run([sys.executable, str(ROOT / "seed.py")], cwd=ROOT)
        if seeded.returncode != 0:
            print("\nDemo setup failed. Review the error above.")
            input("Press Enter to close...")
            return

    print("\nStarting RecoverLink. Keep this window open while using the website.")
    print("Website: " + URL)
    threading.Thread(target=open_browser, daemon=True).start()
    try:
        subprocess.run([sys.executable, str(APP)], cwd=ROOT)
    except KeyboardInterrupt:
        pass
    print("\nRecoverLink has stopped.")
    input("Press Enter to close...")


if __name__ == "__main__":
    main()
