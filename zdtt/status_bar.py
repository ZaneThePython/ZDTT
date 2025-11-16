"""
Status bar, scroll region, and resize handling utilities for ZDTT.
All functions operate on the provided terminal instance.
"""
import sys
import shutil
from datetime import datetime


def set_scroll_region(terminal):
    try:
        rows = shutil.get_terminal_size().lines
        rows = max(rows, 2)
        sys.stdout.write(f"\033[2;{rows}r")
        sys.stdout.write("\033[1;1H")
        sys.stdout.write("\033[2K")
        sys.stdout.write("\033[2;1H")
        sys.stdout.flush()
        terminal.scroll_region_set = True
    except Exception:
        terminal.scroll_region_set = False


def reset_scroll_region(terminal):
    if not terminal.scroll_region_set:
        return
    sys.stdout.write("\033[r")
    sys.stdout.flush()
    terminal.scroll_region_set = False


def build_status_bar_text(terminal):
    left_text = f"{terminal.COLOR_BOLD}ZDTT{terminal.COLOR_RESET} by {terminal.COLOR_BOLD}ZaneDev{terminal.COLOR_RESET}"
    time_str = datetime.now().strftime("%I:%M %p")
    plain_left = "ZDTT by ZaneDev"
    plain_time = time_str

    try:
        term_size = shutil.get_terminal_size()
        width = max(1, term_size.columns)
    except Exception:
        width = max(1, len(plain_left) + len(plain_time) + 6)

    min_content_width = len(plain_left) + len(plain_time) + 5
    padding = 0 if width < min_content_width else width - min_content_width
    separator = f"{terminal.COLOR_DIM}│{terminal.COLOR_RESET}"
    bar_content = f" {left_text} {' ' * padding}{separator} {terminal.COLOR_BRIGHT_WHITE}{time_str}{terminal.COLOR_RESET} "
    actual_display_len = len(plain_left) + len(plain_time) + padding + 5

    if actual_display_len < width:
        trailing_spaces = width - actual_display_len
        bar_content = bar_content.rstrip() + ' ' * trailing_spaces
    elif actual_display_len > width:
        padding = max(0, width - min_content_width)
        bar_content = f" {left_text} {' ' * padding}{separator} {terminal.COLOR_BRIGHT_WHITE}{time_str}{terminal.COLOR_RESET} "
        actual_display_len = len(plain_left) + len(plain_time) + padding + 5
        if actual_display_len < width:
            trailing_spaces = width - actual_display_len
            bar_content = bar_content.rstrip() + ' ' * trailing_spaces
        else:
            if width < len(plain_left) + 10:
                bar_content = f" {left_text} {separator} {terminal.COLOR_BRIGHT_WHITE}{time_str[:8]}{terminal.COLOR_RESET} "
                bar_content = bar_content[:width] if len(bar_content) > width else bar_content

    bg_code, fg_code = terminal.STATUS_BAR_COLORS_LOOKUP()
    result = f"\033[{bg_code}m\033[{fg_code}m{bar_content}\033[0m"
    if len(result) > width * 2:
        simple_bar = f" ZDTT by ZaneDev | {time_str} "
        simple_bar = simple_bar[:width] if len(simple_bar) > width else simple_bar.ljust(width)
        result = f"\033[{bg_code}m\033[{fg_code}m{simple_bar}\033[0m"
    return result


def render_status_bar(terminal):
    try:
        try:
            term_size = shutil.get_terminal_size()
            max_width = term_size.columns
        except Exception:
            max_width = 80
        bar_text = build_status_bar_text(terminal)
        if len(bar_text) > max_width * 3:
            bar_text = build_status_bar_text(terminal)
        sys.stdout.write("\033[s")
        sys.stdout.write("\033[1;1H")
        sys.stdout.write("\033[2K")
        sys.stdout.write("\033[0m")
        sys.stdout.write(bar_text)
        sys.stdout.write("\033[0m")
        sys.stdout.write(f"\033[{max_width}G")
        sys.stdout.write("\033[u")
        sys.stdout.flush()
    except Exception:
        pass


def status_bar_loop(terminal):
    while not terminal.status_bar_stop_event.is_set():
        render_status_bar(terminal)
        if terminal.status_bar_stop_event.wait(2):
            break


def start_status_bar_thread(terminal):
    if terminal.status_bar_thread and terminal.status_bar_thread.is_alive():
        return
    terminal.status_bar_stop_event.clear()
    terminal.status_bar_thread = terminal._spawn_thread(target=lambda: status_bar_loop(terminal), name="ZDTTStatusBar")
    terminal.status_bar_thread.start()


def initialize_status_bar(terminal):
    set_scroll_region(terminal)
    start_status_bar_thread(terminal)
    render_status_bar(terminal)


def shutdown_status_bar(terminal):
    terminal.status_bar_stop_event.set()
    if terminal.status_bar_thread and terminal.status_bar_thread.is_alive():
        terminal.status_bar_thread.join(timeout=0.5)
    terminal.status_bar_thread = None
    reset_scroll_region(terminal)


def handle_resize(terminal, signum=None, frame=None):
    if not terminal.resize_lock.acquire(blocking=False):
        return
    try:
        import time as time_module
        time_module.sleep(0.05)
        reset_scroll_region(terminal)
        set_scroll_region(terminal)
        try:
            sys.stdout.write("\033[1;1H")
            sys.stdout.write("\033[2K")
            sys.stdout.write("\033[0m")
            sys.stdout.flush()
        except Exception:
            pass
        render_status_bar(terminal)
        try:
            term_size = shutil.get_terminal_size()
            sys.stdout.write(f"\033[{term_size.lines};1H")
            sys.stdout.flush()
        except Exception:
            pass
    except Exception:
        pass
    finally:
        terminal.resize_lock.release()



