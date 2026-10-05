"""
Window utilities for Kingdom AI Studio on Windows.
Provides Desktop Window Manager (DWM) theming (immersive dark mode, title bar caption color)
and native window management (minimize, maximize/restore).
"""
import sys
import os
import ctypes
from typing import Optional

def find_kingdom_hwnd(target_title: str = "Kingdom AI Studio") -> Optional[int]:
    """Finds the HWND of the Kingdom AI Studio desktop window."""
    if sys.platform != "win32":
        return None

    try:
        user32 = ctypes.windll.user32
        
        # Ensure interactive desktop attachment
        try:
            h_winsta = user32.OpenWindowStationW("WinSta0", False, 0x10000000)
            if h_winsta:
                user32.SetProcessWindowStation(h_winsta)
            h_desk = user32.OpenDesktopW("Default", 0, False, 0x10000000)
            if h_desk:
                user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

        found_hwnd = [None]
        current_pid = os.getpid()

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_proc(hwnd, lParam):
            if not user32.IsWindowVisible(hwnd):
                return True

            lpdw_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
            if lpdw_pid.value == current_pid:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if target_title.lower() in buff.value.lower():
                        found_hwnd[0] = hwnd
                        return False
            return True

        user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
        return found_hwnd[0]
    except Exception:
        return None


def apply_dwm_dark_theme(hwnd: Optional[int] = None, canvas_color: int = 0x00181818) -> bool:
    """
    Applies Windows DWM attributes to blend the native title bar with application dark styling.
    - DWMWA_USE_IMMERSIVE_DARK_MODE (20, legacy 19)
    - DWMWA_CAPTION_COLOR (35) [Win 11]
    - DWMWA_TEXT_COLOR (36) [Win 11]
    - DWMWA_BORDER_COLOR (34) [Win 11]
    """
    if sys.platform != "win32":
        return False

    if hwnd is None:
        hwnd = find_kingdom_hwnd()
    if not hwnd:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        
        # 1. Immersive Dark Mode (Win 10 19041+ & Win 11)
        val = ctypes.c_int(1)
        # Try modern attribute 20 first, fallback to 19
        if dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val)) != 0:
            dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))

        # 2. Windows 11 Custom Title Bar Caption Color (BGR format: 0x00BBGGRR)
        caption_color = ctypes.c_uint32(canvas_color)
        dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color))

        # 3. Windows 11 Title Bar Text Color (soft gray/white text)
        text_color = ctypes.c_uint32(0x00D4D4D4)
        dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))

        # 4. Windows 11 Window Border Color (subtle border)
        border_color = ctypes.c_uint32(0x00282828)
        dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border_color), ctypes.sizeof(border_color))

        return True
    except Exception:
        return False


def minimize_window(hwnd: Optional[int] = None) -> bool:
    """Minimizes the studio window."""
    if sys.platform != "win32":
        return False
    hwnd = hwnd or find_kingdom_hwnd()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
        return True
    return False


def toggle_maximize_window(hwnd: Optional[int] = None) -> bool:
    """Toggles maximize and restore state of the studio window."""
    if sys.platform != "win32":
        return False
    hwnd = hwnd or find_kingdom_hwnd()
    if hwnd:
        user32 = ctypes.windll.user32
        if user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
        else:
            user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE = 3
        return True
    return False
