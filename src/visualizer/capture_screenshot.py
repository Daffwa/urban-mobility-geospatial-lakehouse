"""
Automated High-Resolution Screenshot Capture for Urban Mobility 3D Map Visualizer.
Uses Microsoft Edge in headless mode with WebGL support.
"""

import os
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENSHOT_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

TARGET_URL = "http://localhost:8060"
LOCAL_OUTPUT = os.path.join(SCREENSHOT_DIR, "urban_mobility_3d_dashboard.png")
ARTIFACT_OUTPUT = r"C:\Users\mdaff\.gemini\antigravity\brain\6a8c54b5-a4ef-4566-b874-39392fb63923\urban_mobility_3d_dashboard.png"

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def capture_screenshot():
    print("=" * 60)
    print(f"Capturing 3D Visualizer Screenshot from {TARGET_URL}...")
    print("=" * 60)
    
    cmd = [
        EDGE_PATH,
        "--headless=new",
        "--enable-webgl",
        "--use-gl=angle",
        "--ignore-gpu-blocklist",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--window-size=1920,1080",
        "--virtual-time-budget=8000",
        f"--screenshot={LOCAL_OUTPUT}",
        TARGET_URL
    ]
    
    print("[>] Running Edge headless process...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(f"    Exit code: {res.returncode}")
    
    if os.path.exists(LOCAL_OUTPUT):
        size_kb = os.path.getsize(LOCAL_OUTPUT) / 1024
        print(f"[+] Screenshot captured successfully: {LOCAL_OUTPUT} ({size_kb:.2f} KB)")
        
        # Copy to artifact directory for UI display
        try:
            import shutil
            shutil.copyfile(LOCAL_OUTPUT, ARTIFACT_OUTPUT)
            print(f"[+] Copied to Artifact directory: {ARTIFACT_OUTPUT}")
        except Exception as e:
            print(f"[!] Warning copying to artifact directory: {e}")
            
        return LOCAL_OUTPUT
    else:
        print(f"[!] Screenshot file was not created. Stdout: {res.stdout}, Stderr: {res.stderr}")
        return None


if __name__ == "__main__":
    capture_screenshot()
