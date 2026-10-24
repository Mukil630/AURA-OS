"""
JARVIS Visible Window Spawner & Screen Splitter
Ensures processes are physically spawned on Mukil's visible interactive desktop (WinSta0\\default)
and arranged side-by-side or brought to foreground.
"""
import time
import win32process
import win32service
import win32gui
import win32con
import sys

def attach_to_user_desktop():
    hwinsta = win32service.OpenWindowStation('WinSta0', False, 0x10000000)
    hwinsta.SetProcessWindowStation()
    hdesk = win32service.OpenDesktop('default', 0, False, 0x10000000)
    hdesk.SetThreadDesktop()
    return hdesk

def snap_terminal_left():
    hdesk = attach_to_user_desktop()
    term_hwnd = None
    def cb(hwnd, _):
        nonlocal term_hwnd
        if win32gui.IsWindowVisible(hwnd):
            txt = win32gui.GetWindowText(hwnd)
            if 'agy-auto' in txt or 'Command Prompt' in txt:
                term_hwnd = hwnd
    win32gui.EnumDesktopWindows(hdesk, cb, None)
    if term_hwnd:
        win32gui.ShowWindow(term_hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(term_hwnd, 0, 0, 768, 912, True)
        print(f"[JARVIS] Snapped Terminal (HWND {term_hwnd}) to LEFT half (0, 0, 768, 912)")
    return term_hwnd

def spawn_and_snap_chrome(url="https://www.google.com"):
    # Step 1: Snap terminal to left
    snap_terminal_left()

    # Step 2: Spawn Chrome on WinSta0\default
    si = win32process.STARTUPINFO()
    si.lpDesktop = r"WinSta0\default"
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    cmd = f'"{chrome_path}" --new-window "{url}"'
    
    try:
        hProcess, hThread, dwProcessId, dwThreadId = win32process.CreateProcess(
            None, cmd, None, None, 0, 0, None, None, si
        )
        print(f"[JARVIS] Spawned Chrome on physical desktop with PID {dwProcessId}")
    except Exception as e:
        print(f"[!] CreateProcess failed: {e}")
        return

    # Step 3: Wait for window to appear and snap to Right half
    time.sleep(2.0)
    hdesk = attach_to_user_desktop()
    chrome_hwnd = None
    for attempt in range(5):
        def cb(hwnd, _):
            nonlocal chrome_hwnd
            if win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd)
                if 'Chrome' in txt or 'Google' in txt:
                    chrome_hwnd = hwnd
        win32gui.EnumDesktopWindows(hdesk, cb, None)
        if chrome_hwnd:
            break
        time.sleep(0.5)

    if chrome_hwnd:
        win32gui.ShowWindow(chrome_hwnd, win32con.SW_RESTORE)
        win32gui.MoveWindow(chrome_hwnd, 768, 0, 768, 912, True)
        win32gui.SetForegroundWindow(chrome_hwnd)
        print(f"[JARVIS] Physical Chrome window (HWND {chrome_hwnd}) placed on RIGHT half (768, 0, 768, 912) in FRONT!")
    else:
        print("[!] Chrome process started but top-level window not yet detected.")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"
    spawn_and_snap_chrome(url)
