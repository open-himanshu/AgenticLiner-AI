"""
AgenticLiner - Live Server & Public Tunnel Launcher
Starts FastAPI Backend and generates a secure public HTTPS link via Cloudflare Tunnel.
Anyone on any mobile phone or computer can open the public link without local Wi-Fi limitations.
"""

import sys
import os
import re
import time
import subprocess
import signal

# Ensure Windows stdout handles UTF-8 / symbols safely
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_PATH = os.path.join(ROOT_DIR, "cloudflared.exe")

def log(msg=""):
    print(msg, flush=True)

def main():
    log("\n" + "="*70)
    log("[*] STARTING AGENTICLINER LIVE SERVER...")
    log("="*70)

    if not os.path.exists(CLOUDFLARED_PATH):
        log(f"[!] Error: cloudflared.exe not found at {CLOUDFLARED_PATH}")
        sys.exit(1)

    # 1. Start FastAPI / Uvicorn Server
    log("[*] Launching Uvicorn backend on http://127.0.0.1:8000 ...")
    uvicorn_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Give uvicorn a moment to bind
    time.sleep(1.5)

    # 2. Start Cloudflare Tunnel
    log("[*] Creating secure public HTTPS tunnel via Cloudflare...")
    cf_proc = subprocess.Popen(
        [CLOUDFLARED_PATH, "tunnel", "--url", "http://127.0.0.1:8000"],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    public_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read output to capture public URL
    start_time = time.time()
    while time.time() - start_time < 20:
        line = cf_proc.stdout.readline()
        if not line:
            continue
        match = url_pattern.search(line)
        if match:
            public_url = match.group(0)
            break

    if not public_url:
        log("[!] Warning: Could not automatically parse Cloudflare URL in 20s.")
        log("You can still use Localhost: http://127.0.0.1:8000")
    else:
        log("\n" + "="*70)
        log(">>> AGENTICLINER IS NOW PUBLICLY ACCESSIBLE! <<<")
        log("="*70)
        log("\n>>> SHARE THIS PUBLIC LINK WITH YOUR FRIENDS / EVALUATORS:\n")
        log(f"    {public_url}")
        log(f"\n[+] Local Machine URL: http://127.0.0.1:8000\n")
        log(">>> SABHI DASHBOARDS AUR ROLES EK HI LINK ME AVAILABLE HAIN:")
        log(f"    - Login / Gateway (4 Role Buttons): {public_url}/login")
        log(f"    - Student Registration & Gate Pass: {public_url}/register")
        log(f"    - Supervisor Dean Portal:          {public_url}/supervisor")
        log(f"    - Organiser Operations Hub:         {public_url}/organiser")
        log(f"    - Campus Data Manager (Catalog):    {public_url}/data-manager")
        log(f"    - Student Portal & Live QR Pass:    {public_url}/participant")
        log(f"    - Intelligent Timetable (OR-Tools): {public_url}/schedule")
        log(f"    - Feedback & Sentiment Analytics:   {public_url}/analytics")
        log("="*70)
        log("[i] TIP: Server ko band karne ke liye 'CTRL + C' dabayein.\n")

    def shutdown(sig, frame):
        log("\n[*] Shutting down server and public tunnel...")
        try:
            cf_proc.terminate()
            uvicorn_proc.terminate()
        except Exception:
            pass
        log("[+] Server successfully stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            if uvicorn_proc.poll() is not None:
                print("[!] Uvicorn backend stopped unexpectedly.")
                break
            if cf_proc.poll() is not None:
                print("[!] Cloudflare tunnel disconnected.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
