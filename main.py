#!/usr/bin/env python3
import evdev
from evdev import InputDevice, ecodes
import os
import subprocess
import signal
import threading
import queue
import time
import shutil
import argparse
import glob

__version__ = "0.1.0"

BongoWindow = None
stop_event = threading.Event()
keyboard_stop_event = threading.Event()
key_queue = queue.Queue()
keyboard_threads = []
keyboard_devices = []

TARGET_WINDOW_NAME = 'TapTapLoot'
TARGET_DISPLAY = ':10'

def get_xauth_path():
    """Dynamically find the current taptaploot xauth file"""
    matches = glob.glob('/tmp/taptaploot-xauth.*')
    if matches:
        return matches[0]
    return None

def get_xenv():
    """Get environment dict for xdotool calls targeting the game display"""
    xauth = get_xauth_path()
    env = {**os.environ, 'DISPLAY': TARGET_DISPLAY}
    if xauth:
        env['XAUTHORITY'] = xauth
    return env

def get_xdotool_keyname(keycode):
    key_name = ecodes.KEY[keycode]
    if key_name.startswith('KEY_'):
        key_name = key_name[4:]
    elif key_name.startswith('BTN_'):
        key_name = key_name[4:]
    key_name = key_name.lower()
    special_keys = {
        'leftctrl': 'ctrl',
        'rightctrl': 'ctrl',
        'leftshift': 'shift',
        'rightshift': 'shift',
        'leftalt': 'alt',
        'rightalt': 'alt',
        'leftmeta': 'super',
        'rightmeta': 'super',
        'enter': 'Return',
        'esc': 'Escape',
        'backspace': 'BackSpace',
        'tab': 'Tab',
        'capslock': 'Caps_Lock',
    }
    return special_keys.get(key_name, key_name)

def find_game_window():
    """Find the TapTapLoot window on the game display"""
    try:
        env = get_xenv()
        result = subprocess.getoutput(
            f"DISPLAY={TARGET_DISPLAY} XAUTHORITY={env.get('XAUTHORITY', '')} "
            f"xdotool search --name '{TARGET_WINDOW_NAME}'"
        )
        if not result.strip():
            return None

        for window_id in result.strip().split('\n'):
            window_name = subprocess.getoutput(
                f"DISPLAY={TARGET_DISPLAY} XAUTHORITY={env.get('XAUTHORITY', '')} "
                f"xdotool getwindowname {window_id}"
            ).strip()
            if window_name == TARGET_WINDOW_NAME:
                return window_id

        # No exact match, return first result
        return result.strip().split('\n')[0]
    except:
        pass
    return None

def send_keys_to_game(keys):
    """Send batched keypresses to the game window"""
    if not keys or not BongoWindow:
        return

    env = get_xenv()
    batch_size = 4
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i+batch_size]

        cmd_keydown = ['xdotool', 'keydown', '--window', BongoWindow] + batch
        cmd_keyup = ['xdotool', 'keyup', '--window', BongoWindow] + batch

        try:
            result = subprocess.run(cmd_keydown, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                continue
            time.sleep(0.01)
            subprocess.run(cmd_keyup, capture_output=True, text=True, env=env)
        except Exception:
            pass

def replace_duplicate_keys(keys):
    if not keys:
        return []
    replacement_pool = list('abcdefghijklmnopqrstuvwxyz')
    seen = set()
    result = []
    for key in keys:
        if key in seen:
            for replacement in replacement_pool:
                if replacement not in seen:
                    result.append(replacement)
                    seen.add(replacement)
                    break
            else:
                result.append(key)
        else:
            result.append(key)
            seen.add(key)
    return result

def batch_sender():
    while not stop_event.is_set():
        time.sleep(0.2)
        keys = []
        while True:
            try:
                key = key_queue.get_nowait()
                keys.append(key)
            except queue.Empty:
                break
        if keys:
            replaced_keys = replace_duplicate_keys(keys)
            send_keys_to_game(replaced_keys)

def is_keyboard(device):
    capabilities = device.capabilities()
    if ecodes.EV_KEY not in capabilities:
        return False
    keys = capabilities[ecodes.EV_KEY]
    mouse_buttons = [
        ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE,
        ecodes.BTN_SIDE, ecodes.BTN_EXTRA, ecodes.BTN_FORWARD,
        ecodes.BTN_BACK, ecodes.BTN_MOUSE,
    ]
    for btn in mouse_buttons:
        if btn in keys:
            return False
    if ecodes.BTN_TOUCH in keys or ecodes.BTN_TOOL_FINGER in keys:
        return False
    keyboard_keys = [
        ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C,
        ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_ESC,
    ]
    for key in keyboard_keys:
        if key in keys:
            return True
    return False

def monitor_keyboard(device):
    try:
        for event in device.read_loop():
            if keyboard_stop_event.is_set() or stop_event.is_set():
                break
            if event.type == ecodes.EV_KEY and event.value == 1:
                try:
                    key_name = get_xdotool_keyname(event.code)
                    key_queue.put(key_name)
                except (KeyError, ValueError):
                    pass
    except (OSError, IOError):
        pass

def start_keyboard_monitoring():
    global keyboard_threads, keyboard_devices
    keyboard_stop_event.clear()
    all_devices = [InputDevice(path) for path in evdev.list_devices()]
    keyboards = [device for device in all_devices if is_keyboard(device)]
    if not keyboards:
        print("  [Warning] No keyboard devices found")
        return False
    print(f"  Found {len(keyboards)} keyboard device(s)")
    keyboard_devices = keyboards
    keyboard_threads = []
    for kb in keyboards:
        thread = threading.Thread(target=monitor_keyboard, args=(kb,), daemon=True)
        thread.start()
        keyboard_threads.append(thread)
    return True

def stop_keyboard_monitoring():
    global keyboard_threads, keyboard_devices
    keyboard_stop_event.set()
    for kb in keyboard_devices:
        try:
            kb.close()
        except Exception:
            pass
    for thread in keyboard_threads:
        thread.join(timeout=1.0)
    keyboard_threads = []
    keyboard_devices = []

def window_monitor():
    global BongoWindow
    last_window_state = None

    while not stop_event.is_set():
        new_window = find_game_window()

        if new_window and not last_window_state:
            BongoWindow = new_window
            print(f"\n✓ Connected to {TARGET_WINDOW_NAME} window (ID: {BongoWindow})")
            print("  Starting keyboard monitoring...")
            if start_keyboard_monitoring():
                print("  ✓ Keyboard monitoring started\n")
            last_window_state = True

        elif not new_window and last_window_state:
            print(f"\n⚠ {TARGET_WINDOW_NAME} window closed")
            print("  Stopping keyboard monitoring...")
            stop_keyboard_monitoring()
            print("  ✓ Waiting for window to reappear...\n")
            BongoWindow = None
            last_window_state = False

        elif not new_window and last_window_state is None:
            print(f"⚠ {TARGET_WINDOW_NAME} window not found")
            print("  Waiting... (checks every 10s)\n")
            BongoWindow = None
            last_window_state = False

        elif new_window and last_window_state:
            if BongoWindow != new_window:
                BongoWindow = new_window
                print(f"\n✓ Window ID updated (ID: {BongoWindow})\n")

        stop_event.wait(10)

def main():
    print(f"BongoCatXP - TapTapLoot edition\n")

    def signal_handler(signum, frame):
        print("\nStopping...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    xauth = get_xauth_path()
    if xauth:
        print(f"Using xauth: {xauth}")
    else:
        print("⚠ Warning: no taptaploot xauth file found in /tmp — is the game running?")

    print("Starting window monitor (Ctrl+C to stop)\n")

    sender_thread = threading.Thread(target=batch_sender, daemon=True)
    sender_thread.start()

    monitor_thread = threading.Thread(target=window_monitor, daemon=True)
    monitor_thread.start()

    try:
        stop_event.wait()
    finally:
        print("Stopping keyboard monitoring...")
        stop_keyboard_monitoring()
        print("Done")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='bongocatxp',
        description='BongoCat X11 Proxy - TapTapLoot edition'
    )
    parser.add_argument('--version', action='version', version=f'BongoCatXP {__version__}')
    args = parser.parse_args()

    if not shutil.which('xdotool'):
        print("Error: xdotool not found — install with: sudo pacman -S xdotool")
        exit(1)

    if not os.access('/dev/input/event0', os.R_OK):
        print("No permission to read input devices.")
        print("Run: sudo usermod -aG input $USER  (then log out and back in)")
        print(f"Or temporarily: sudo python3 {__file__}")
        exit(1)

    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
