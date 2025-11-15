#!/usr/bin/env python3
"""
ZDTT Terminal - A custom terminal interface
Only works on Debian-based or Arch Linux systems
"""

import os
import sys
import getpass
import subprocess
import shutil
import readline
import glob
import atexit
import logging
import threading
import json
import shlex
import signal
from datetime import datetime
import urllib.request
import urllib.error
import time as time_module


SUPPORTED_DEBIAN_IDS = {
    'debian',
    'ubuntu',
    'linuxmint',
    'mint',
    'pop',
    'pop-os',
    'pop_os',
    'elementary',
    'zorin',
    'kali',
    'parrot',
    'mx',
    'mx-linux',
    'deepin',
    'peppermint',
    'raspbian',
    'neon',
}

SUPPORTED_ARCH_IDS = {
    'arch',
    'archlinux',
    'manjaro',
    'endeavouros',
    'endeavour',
    'arcolinux',
    'garuda',
    'artix',
    'blackarch',
    'chakra',
}

STATUS_BAR_COLORS = {
    'blue': ('44', '97'),
    'red': ('41', '97'),
    'green': ('42', '30'),
    'cyan': ('46', '30'),
    'magenta': ('45', '97'),
    'yellow': ('43', '30'),
    'white': ('47', '30'),
    'black': ('40', '97'),
}


def _parse_os_release():
    """Return a dict of fields from /etc/os-release if available"""
    data = {}
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                value = value.strip().strip('"')
                data[key] = value
    except FileNotFoundError:
        pass
    return data


def _collect_tokens(*values):
    """Normalize distro identifiers for comparison"""
    tokens = set()
    for value in values:
        if not value:
            continue
        normalized = value.replace('"', '').strip().lower()
        if not normalized:
            continue
        # Keep the raw normalized value plus its dashed/underscored variants split
        tokens.add(normalized)
        delimiters_replaced = normalized.replace('-', ' ').replace('_', ' ')
        for part in delimiters_replaced.split():
            if part:
                tokens.add(part)
    return tokens


def _detect_supported_distro():
    """Return distro identifier: 'debian', 'arch', or 'other'"""
    if os.path.exists('/etc/debian_version'):
        return 'debian'
    
    arch_markers = (
        '/etc/arch-release',
        '/etc/artix-release',
    )
    if any(os.path.exists(path) for path in arch_markers):
        return 'arch'
    
    os_release = _parse_os_release()
    tokens = _collect_tokens(os_release.get('ID'), os_release.get('ID_LIKE'))
    
    if tokens & SUPPORTED_DEBIAN_IDS:
        return 'debian'
    if tokens & SUPPORTED_ARCH_IDS:
        return 'arch'
    
    # Fallback to package manager detection
    if shutil.which('apt-get'):
        return 'debian'
    if shutil.which('pacman'):
        return 'arch'
    
    return 'other'


def _prompt_distro_override(detected_distro):
    """Allow user to override detected distro."""
    label_map = {
        'debian': "Debian-based",
        'arch': "Arch-based",
        'other': "Unsupported/Other",
    }
    print("=" * 60)
    print(f"Detected distribution: {label_map.get(detected_distro, 'Unknown')}")
    print("If this is incorrect, enter one of: debian / arch / other.")
    print("Press Enter to accept the detected value.")
    override = input("Override distribution (leave blank to keep): ").strip().lower()
    
    if override in ('debian', 'arch', 'other'):
        return override
    
    if override:
        print(f"Unknown override '{override}'. Using detected value.")
    
    return detected_distro


def _load_saved_distro():
    """Load saved distro preference from config file."""
    config_file = os.path.expanduser("~/.zdtt/config.json")
    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
            saved_distro = data.get('distro')
            if saved_distro in ('debian', 'arch', 'other'):
                return saved_distro
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return None

def _save_distro_preference(distro):
    """Save distro preference to config file."""
    config_file = os.path.expanduser("~/.zdtt/config.json")
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    data = {}
    try:
        with open(config_file, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    
    data['distro'] = distro
    
    with open(config_file, 'w') as f:
        json.dump(data, f, indent=2)

def check_system_compatibility():
    """Detect supported distributions and warn when unsupported"""
    # Check for saved distro preference first
    saved_distro = _load_saved_distro()
    if saved_distro:
        # Use saved preference, skip prompts
        return saved_distro
    
    # Check if running on Linux
    if sys.platform != 'linux':
        print("=" * 60)
        print("⚠️  WARNING: ZDTT Terminal is designed for Linux systems")
        print(f"   Detected platform: {sys.platform}")
        print("=" * 60)
        print("ZDTT may not work correctly on your system.")
        print("Some features may be unavailable or broken.")
        print()
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Installation cancelled.")
            sys.exit(0)
        distro = 'other'
        _save_distro_preference(distro)
        return distro
    
    # Detect supported distributions
    distro = _detect_supported_distro()
    
    if distro not in ('debian', 'arch'):
        # Unsupported distribution
        print("=" * 60)
        print("⚠️  WARNING: Unsupported Distribution Detected")
        print("=" * 60)
        print("ZDTT Terminal is optimized for Debian-based and Arch Linux systems.")
        print()
        print("Running on your current system may result in:")
        print("  • Some commands may not work as expected")
        print("  • Auto-install features may fail")
        print("  • Reduced plugin compatibility")
        print("  • Package management commands unavailable")
        print()
        response = input("Continue installation? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Installation cancelled.")
            sys.exit(0)
    
    # Offer override regardless of detection
    distro = _prompt_distro_override(distro)
    
    # Save the selected distro preference
    _save_distro_preference(distro)
    
    return distro


class ZDTTTerminal:
    def __init__(self, distro='debian'):
        self.username = getpass.getuser()
        self.running = True
        self.current_dir = os.getcwd()
        self.distro = distro
        self.is_debian = distro == 'debian'
        self.is_arch = distro == 'arch'
        self.is_supported = self.is_debian or self.is_arch
        self.zdtt_dir = os.path.expanduser("~/.zdtt")
        self.history_file = os.path.expanduser("~/.zdtt_history")
        self.plugin_dir = os.path.join(self.zdtt_dir, "plugins")
        self.log_file = os.path.join(self.zdtt_dir, "plugin_errors.log")
        self.banner_file = os.path.join(self.zdtt_dir, "banner.txt")
        self.aliases_file = os.path.join(self.zdtt_dir, "aliases")
        self.config_file = os.path.join(self.zdtt_dir, "config.json")
        self.status_bar_color = 'blue'
        self.status_bar_thread = None
        self.status_bar_stop_event = threading.Event()
        self.scroll_region_set = False
        self.plugin_command_names = set()
        self.update_check_thread = None
        self.resize_lock = threading.Lock()  # Lock for resize operations
        
        # Setup logging for plugins
        self.setup_logging()
        
        # Load user aliases
        self.aliases = {}
        self.load_aliases()
        
        # Read version from version.txt
        self.version = self.read_version()
        
        # Load user preferences (status bar color, etc.)
        self.load_preferences()
        
        # ANSI color codes - Enhanced palette
        self.COLOR_RESET = '\033[0m'
        self.COLOR_BOLD = '\033[1m'
        self.COLOR_DIM = '\033[2m'
        self.COLOR_ITALIC = '\033[3m'
        
        # Standard colors
        self.COLOR_BLACK = '\033[30m'
        self.COLOR_RED = '\033[31m'
        self.COLOR_GREEN = '\033[32m'
        self.COLOR_YELLOW = '\033[33m'
        self.COLOR_BLUE = '\033[34m'
        self.COLOR_MAGENTA = '\033[35m'
        self.COLOR_CYAN = '\033[36m'
        self.COLOR_WHITE = '\033[37m'
        
        # Bright colors
        self.COLOR_BRIGHT_BLACK = '\033[90m'
        self.COLOR_BRIGHT_RED = '\033[91m'
        self.COLOR_BRIGHT_GREEN = '\033[92m'
        self.COLOR_BRIGHT_YELLOW = '\033[93m'
        self.COLOR_BRIGHT_BLUE = '\033[94m'
        self.COLOR_BRIGHT_MAGENTA = '\033[95m'
        self.COLOR_BRIGHT_CYAN = '\033[96m'
        self.COLOR_BRIGHT_WHITE = '\033[97m'
        
        # Accent colors (using bright variants for better visibility)
        self.COLOR_ACCENT = '\033[96m'  # Bright cyan
        self.COLOR_ACCENT2 = '\033[94m'  # Bright blue
        self.COLOR_SUCCESS = '\033[92m'  # Bright green
        self.COLOR_WARNING = '\033[93m'  # Bright yellow
        self.COLOR_ERROR = '\033[91m'    # Bright red
        self.COLOR_INFO = '\033[96m'      # Bright cyan
        
        # Background colors
        self.BG_BLACK = '\033[40m'
        self.BG_RED = '\033[41m'
        self.BG_GREEN = '\033[42m'
        self.BG_YELLOW = '\033[43m'
        self.BG_BLUE = '\033[44m'
        self.BG_MAGENTA = '\033[45m'
        self.BG_CYAN = '\033[46m'
        self.BG_WHITE = '\033[47m'
        self.BG_BRIGHT_CYAN = '\033[106m'
        
        self.commands = {
            'help': self.cmd_help,
            'clear': self.cmd_clear,
            'exit': self.cmd_exit,
            'quit': self.cmd_quit,
            'about': self.cmd_about,
            'echo': self.cmd_echo,
            'history': self.cmd_history,
            'plugins': self.cmd_plugins,
            'alias': self.cmd_alias,
            'unalias': self.cmd_unalias,
            'zps': self.cmd_zps,
            'time': self.cmd_time,
            'statusbar': self.cmd_statusbar,
            'update': self.cmd_update,
            # System commands
            'ls': self.cmd_ls,
            'pwd': self.cmd_pwd,
            'cd': self.cmd_cd,
            'cat': self.cmd_cat,
            'nano': self.cmd_nano,
            'sysfetch': self.cmd_sysfetch,
            'mkdir': self.cmd_mkdir,
            'touch': self.cmd_touch,
            'rm': self.cmd_rm,
            'mv': self.cmd_mv,
            'cp': self.cmd_cp,
            'whoami': self.cmd_whoami,
            'date': self.cmd_date,
            'uname': self.cmd_uname,
            'grep': self.cmd_grep,
            # Python commands
            'python': self.cmd_python,
            'python3': self.cmd_python3,
            'pip': self.cmd_pip,
            'pip3': self.cmd_pip3,
        }
        
        # Setup readline history and tab completion
        self.setup_readline()
        
        # Load plugins
        self.load_plugins()
        
        # Kick off async update check
        self.start_update_check()
    
    def setup_logging(self):
        """Setup logging for plugin errors"""
        # Create .zdtt directory if it doesn't exist
        os.makedirs(self.zdtt_dir, exist_ok=True)
        
        # Configure logger
        logging.basicConfig(
            filename=self.log_file,
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def read_version(self):
        """Read version from version.txt file"""
        # Try multiple locations for version.txt
        version_paths = [
            os.path.join(os.path.dirname(__file__), 'version.txt'),  # Same dir as script
            os.path.expanduser("~/.local/share/zdtt/version.txt"),  # Installed location
        ]
        
        for path in version_paths:
            try:
                with open(path, 'r') as f:
                    return f.read().strip()
            except FileNotFoundError:
                continue
        
        # Fallback version if file not found
        return "0.0.1.a"
    
    def load_preferences(self):
        """Load user preferences such as status bar color and distro."""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            self.status_bar_color = data.get('status_bar_color', self.status_bar_color)
            # Note: distro is loaded in check_system_compatibility before terminal init
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            logging.warning("Preferences file is corrupted; using defaults.")
    
    def save_preferences(self):
        """Persist user preferences."""
        data = {}
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        data['status_bar_color'] = self.status_bar_color
        # Note: distro is saved in check_system_compatibility
        
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def start_update_check(self):
        """Start the background thread that checks for updates."""
        if self.update_check_thread and self.update_check_thread.is_alive():
            return
        self.update_check_thread = threading.Thread(
            target=self._check_for_updates,
            name="ZDTTUpdateCheck",
            daemon=True,
        )
        self.update_check_thread.start()

    def _check_for_updates(self):
        """Background worker that checks if a new version is available."""
        try:
            # Get remote version
            url = "https://zdtt-sources.zane.org/version.txt"
            with urllib.request.urlopen(url, timeout=2) as response:
                remote_version = response.read().decode('utf-8').strip()
            
            # Compare versions
            if remote_version != self.version:
                print()
                print(f"🔔 Update available! Current: {self.version} → Latest: {remote_version}")
                print("   Run 'zdtt update' from your shell to update")
                print()
        except Exception:
            # Silently fail if we can't check for updates
            pass
    
    def display_banner(self):
        """Display the ZDTT ASCII art banner (or custom banner if available)"""
        print()
        
        # Check terminal size to see if banner will fit
        try:
            term_size = shutil.get_terminal_size()
            # Banner is 44 chars wide and 11 lines tall (including version)
            # Add extra space for compatibility warning if needed
            min_height = 13 if not self.is_supported else 11
            min_width = 44
            
            if term_size.columns < min_width or term_size.lines < min_height:
                # Terminal too small, skip banner and just show minimal header
                print(f"ZDTT Terminal v{self.version}")
                if not self.is_supported:
                    print("⚠️  Unsupported system - limited support")
                print()
                return
        except Exception:
            # If we can't get terminal size, display the banner anyway
            pass
        
        # Check for custom banner
        if os.path.exists(self.banner_file):
            try:
                with open(self.banner_file, 'r') as f:
                    custom_banner = f.read()
                    # Add version at the bottom if not already present
                    if '{version}' in custom_banner:
                        custom_banner = custom_banner.replace('{version}', self.version)
                    print(custom_banner)
                    # Show warning for unsupported systems
                    if not self.is_supported:
                        self._show_compatibility_warning()
                    return
            except Exception as e:
                logging.error(f"Failed to load custom banner: {e}")
                # Fall through to default banner
        
        # Default banner
        banner = f"""
░█████████ ░███████   ░██████████░██████████
      ░██  ░██   ░██      ░██        ░██    
     ░██   ░██    ░██     ░██        ░██    
   ░███    ░██    ░██     ░██        ░██    
  ░██      ░██    ░██     ░██        ░██    
 ░██       ░██   ░██      ░██        ░██    
░█████████ ░███████       ░██        ░██    
                                            
                                            
ZDTT Terminal v{self.version}
"""
        print(banner)
        
        # Show warning for unsupported systems after banner
        if not self.is_supported:
            self._show_compatibility_warning()
    
    def _show_compatibility_warning(self):
        """Show compatibility warning for unsupported systems"""
        if self.is_supported:
            return
        
        print()
        print("⚠️  Running on unsupported system - limited support")
        print("    Tested on Debian-based and Arch Linux distributions.")
        print()
    
    def initialize_status_bar(self):
        """Reserve the first terminal row and start the status bar thread."""
        self._set_scroll_region()
        self._start_status_bar_thread()
        self._render_status_bar()
    
    def shutdown_status_bar(self):
        """Stop the status bar thread and release terminal state."""
        self.status_bar_stop_event.set()
        if self.status_bar_thread and self.status_bar_thread.is_alive():
            self.status_bar_thread.join(timeout=0.5)
        self.status_bar_thread = None
        self._reset_scroll_region()
    
    def _start_status_bar_thread(self):
        if self.status_bar_thread and self.status_bar_thread.is_alive():
            return
        self.status_bar_stop_event.clear()
        self.status_bar_thread = threading.Thread(
            target=self._status_bar_loop,
            name="ZDTTStatusBar",
            daemon=True,
        )
        self.status_bar_thread.start()
    
    def _status_bar_loop(self):
        while not self.status_bar_stop_event.is_set():
            self._render_status_bar()
            if self.status_bar_stop_event.wait(2):
                break
    
    def _render_status_bar(self):
        """Render a single-line status bar with branding and time."""
        try:
            # Get terminal size first to ensure we don't write beyond bounds
            try:
                term_size = shutil.get_terminal_size()
                max_width = term_size.columns
            except Exception:
                max_width = 80  # Fallback
            
            bar_text = self._build_status_bar_text()
            
            # Ensure bar_text doesn't exceed terminal width (safety check)
            # Count visible characters (approximate - ANSI codes don't count)
            # This is a rough check, but better than nothing
            if len(bar_text) > max_width * 3:  # Allow for ANSI codes (rough estimate)
                # Rebuild with safer width
                bar_text = self._build_status_bar_text()
            
            sys.stdout.write("\033[s")          # Save cursor position
            sys.stdout.write("\033[1;1H")       # Move to first row, first column
            sys.stdout.write("\033[2K")         # Clear the entire line
            sys.stdout.write("\033[0m")         # Reset all attributes
            sys.stdout.write(bar_text)
            sys.stdout.write("\033[0m")         # Ensure reset at end
            # Move cursor to end of line to prevent wrapping issues
            sys.stdout.write(f"\033[{max_width}G")  # Move to column max_width
            sys.stdout.write("\033[u")          # Restore cursor
            sys.stdout.flush()
        except Exception:
            # Fallback: just skip rendering if there's an error
            pass
    
    def _build_status_bar_text(self):
        """Render a single-line status bar with enhanced branding and time."""
        left_text = f"{self.COLOR_BOLD}ZDTT{self.COLOR_RESET} by {self.COLOR_BOLD}ZaneDev{self.COLOR_RESET}"
        time_str = datetime.now().strftime("%I:%M %p")
        plain_left = "ZDTT by ZaneDev"
        plain_time = time_str
        
        try:
            # Always get fresh terminal size to handle resizes
            term_size = shutil.get_terminal_size()
            width = term_size.columns
            # Safety: ensure width is at least 1
            width = max(1, width)
        except Exception:
            # Fallback to minimum width if we can't get terminal size
            width = max(1, len(plain_left) + len(plain_time) + 6)
        
        # Calculate the minimum content width (plain text only, no ANSI codes)
        # Format: " ZDTT by ZaneDev | TIME "
        min_content_width = len(plain_left) + len(plain_time) + 5  # 5 = spaces + separator
        
        # Calculate padding to fill the line
        if width < min_content_width:
            # Terminal too narrow, use minimum padding
            padding = 0
        else:
            padding = width - min_content_width
        
        # Build the content (plain text calculation)
        separator = f"{self.COLOR_DIM}│{self.COLOR_RESET}"
        bar_content = f" {left_text} {' ' * padding}{separator} {self.COLOR_BRIGHT_WHITE}{time_str}{self.COLOR_RESET} "
        
        # Calculate actual display length (plain text only)
        actual_display_len = len(plain_left) + len(plain_time) + padding + 5
        
        # Ensure we fill exactly to terminal width (but never exceed it)
        if actual_display_len < width:
            # Add trailing spaces to fill exactly to width
            trailing_spaces = width - actual_display_len
            bar_content = bar_content.rstrip() + ' ' * trailing_spaces
        elif actual_display_len > width:
            # We exceeded width, recalculate with less padding
            padding = max(0, width - min_content_width)
            bar_content = f" {left_text} {' ' * padding}{separator} {self.COLOR_BRIGHT_WHITE}{time_str}{self.COLOR_RESET} "
            actual_display_len = len(plain_left) + len(plain_time) + padding + 5
            if actual_display_len < width:
                trailing_spaces = width - actual_display_len
                bar_content = bar_content.rstrip() + ' ' * trailing_spaces
            else:
                # Still too wide, trim the time if necessary
                if width < len(plain_left) + 10:
                    # Very narrow terminal, just show minimal content
                    bar_content = f" {left_text} {separator} {self.COLOR_BRIGHT_WHITE}{time_str[:8]}{self.COLOR_RESET} "
                    bar_content = bar_content[:width] if len(bar_content) > width else bar_content
        
        # Final safety check: ensure we never exceed terminal width
        # This is approximate since ANSI codes don't count, but better than nothing
        bg_code, fg_code = STATUS_BAR_COLORS.get(self.status_bar_color, ('44', '97'))
        result = f"\033[{bg_code}m\033[{fg_code}m{bar_content}\033[0m"
        
        # If the result is suspiciously long, truncate it
        # (rough heuristic: ANSI codes add ~30-50 chars, so if result > width*2, it's probably wrong)
        if len(result) > width * 2:
            # Emergency fallback: simple status bar
            simple_bar = f" ZDTT by ZaneDev | {time_str} "
            simple_bar = simple_bar[:width] if len(simple_bar) > width else simple_bar.ljust(width)
            result = f"\033[{bg_code}m\033[{fg_code}m{simple_bar}\033[0m"
        
        return result
    
    def _set_scroll_region(self):
        """Reserve the top row for the status bar."""
        try:
            rows = shutil.get_terminal_size().lines
            rows = max(rows, 2)
            sys.stdout.write(f"\033[2;{rows}r")
            sys.stdout.write("\033[1;1H")
            sys.stdout.write("\033[2K")
            sys.stdout.write("\033[2;1H")
            sys.stdout.flush()
            self.scroll_region_set = True
        except Exception:
            self.scroll_region_set = False
    
    def _reset_scroll_region(self):
        """Restore default scrolling behavior."""
        if not self.scroll_region_set:
            return
        sys.stdout.write("\033[r")
        sys.stdout.flush()
        self.scroll_region_set = False
    
    def _handle_resize(self, signum=None, frame=None):
        """Handle terminal resize event (SIGWINCH)."""
        # Use a lock to prevent race conditions
        if not self.resize_lock.acquire(blocking=False):
            # If we can't acquire the lock immediately, skip this resize
            # (another resize is already being handled)
            return
        
        try:
            # Small delay to let terminal settle after resize
            time_module.sleep(0.05)
            
            # Reset scroll region first to clear any corrupted state
            self._reset_scroll_region()
            
            # Update scroll region with new terminal size
            self._set_scroll_region()
            
            # Clear the status bar line completely before redrawing
            try:
                sys.stdout.write("\033[1;1H")       # Move to first row
                sys.stdout.write("\033[2K")         # Clear the entire line
                sys.stdout.write("\033[0m")       # Reset attributes
                sys.stdout.flush()
            except Exception:
                pass
            
            # Force immediate status bar refresh
            self._render_status_bar()
            
            # Ensure cursor is in a safe position
            try:
                term_size = shutil.get_terminal_size()
                sys.stdout.write(f"\033[{term_size.lines};1H")  # Move to last line, first column
                sys.stdout.flush()
            except Exception:
                pass
                
        except Exception:
            # Silently fail if resize handling fails
            pass
        finally:
            self.resize_lock.release()
    
    def setup_readline(self):
        """Setup readline for history and tab completion"""
        # Setup history
        try:
            readline.read_history_file(self.history_file)
        except FileNotFoundError:
            pass
        
        # Set history length
        readline.set_history_length(1000)
        
        # Save history on exit
        atexit.register(readline.write_history_file, self.history_file)
        
        # Setup tab completion
        readline.set_completer(self.complete)
        readline.parse_and_bind("tab: complete")
        
        # Enable arrow key navigation in history
        readline.parse_and_bind("set editing-mode emacs")
    
    def complete(self, text, state):
        """Tab completion function"""
        # Get all possible completions
        options = []
        
        # Get the full line buffer
        line = readline.get_line_buffer()
        
        # If we're at the start or completing a command
        if line.startswith(text) or ' ' not in line[:readline.get_begidx()]:
            # Complete command names (built-in commands and aliases)
            options = [cmd for cmd in self.commands.keys() if cmd.startswith(text)]
            # Add aliases
            options.extend([alias for alias in self.aliases.keys() if alias.startswith(text)])
        else:
            # Complete filenames/directories
            if text.startswith('~'):
                text = os.path.expanduser(text)
            
            # Add glob pattern
            if not text:
                pattern = '*'
            else:
                pattern = text + '*'
            
            try:
                matches = glob.glob(pattern)
                options = matches
            except:
                options = []
        
        # Return the state-th option
        if state < len(options):
            return options[state]
        return None
    
    def load_plugins(self):
        """Load plugin commands from the plugins directory"""
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir, exist_ok=True)
            return

        # Look for Python files in the plugins directory
        plugin_files = glob.glob(os.path.join(self.plugin_dir, "*.py"))
        loaded_count = 0
        failed_count = 0

        for plugin_file in plugin_files:
            try:
                # Get plugin name
                plugin_name = os.path.basename(plugin_file)[:-3]
                
                # Read and execute plugin file
                with open(plugin_file, 'r') as f:
                    plugin_code = f.read()
                
                # Create a namespace for the plugin
                plugin_namespace = {}
                exec(plugin_code, plugin_namespace)
                
                # Look for register_command function
                if 'register_commands' in plugin_namespace:
                    plugin_commands = plugin_namespace['register_commands']()
                    if isinstance(plugin_commands, dict):
                        self.commands.update(plugin_commands)
                        self.plugin_command_names.update(plugin_commands.keys())
                        loaded_count += 1
                    else:
                        raise ValueError("register_commands() must return a dictionary")
                else:
                    raise ValueError("Plugin missing register_commands() function")
                    
            except Exception as e:
                failed_count += 1
                # Log error instead of printing
                logging.error(f"Failed to load plugin '{plugin_name}': {str(e)}")
                logging.error(f"Plugin file: {plugin_file}")
        
        # Show brief status if there were failures
        if failed_count > 0:
            print(f"{self.COLOR_WARNING}⚠ {failed_count} plugin(s) failed to load. Check ~/.zdtt/plugin_errors.log{self.COLOR_RESET}")

    def unload_plugin_commands(self):
        """Remove commands that originated from plugins."""
        for cmd_name in list(self.plugin_command_names):
            self.commands.pop(cmd_name, None)
        self.plugin_command_names.clear()
    
    def load_aliases(self):
        """Load user-defined aliases from file"""
        if not os.path.exists(self.aliases_file):
            return
        
        try:
            with open(self.aliases_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse alias definition: alias_name=command
                    if '=' in line:
                        name, command = line.split('=', 1)
                        name = name.strip()
                        command = command.strip()
                        if name and command:
                            self.aliases[name] = command
        except Exception as e:
            logging.error(f"Failed to load aliases: {e}")
    
    def save_aliases(self):
        """Save aliases to file"""
        try:
            with open(self.aliases_file, 'w') as f:
                f.write("# ZDTT Terminal Aliases\n")
                f.write("# Format: alias_name=command\n")
                f.write("#\n")
                for name, command in sorted(self.aliases.items()):
                    f.write(f"{name}={command}\n")
        except Exception as e:
            logging.error(f"Failed to save aliases: {e}")
            print(f"{self.COLOR_ERROR}Error: Failed to save aliases: {e}{self.COLOR_RESET}")
    
    def expand_aliases(self, command_line):
        """Expand aliases in command line"""
        parts = command_line.strip().split()
        if not parts:
            return command_line
        
        # Check if the first word is an alias
        cmd = parts[0]
        if cmd in self.aliases:
            # Replace the alias with its command
            expanded = self.aliases[cmd]
            # Add any remaining arguments
            if len(parts) > 1:
                expanded += ' ' + ' '.join(parts[1:])
            return expanded
        
        return command_line
    
    def get_prompt(self):
        """Return the custom prompt string with enhanced colors"""
        # Show current directory in prompt
        cwd = os.getcwd()
        # Show ~ for home directory
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            display_path = "~" + cwd[len(home):]
        else:
            display_path = cwd
        
        # Wrap ANSI codes in \001 and \002 so readline knows they're non-printable
        # This fixes line wrapping issues with long commands
        RL_PROMPT_START = '\001'
        RL_PROMPT_END = '\002'
        
        # Create enhanced colorized prompt with gradient-like effect
        # [username in bright green @ ZDTT in bright cyan path in bright blue]=>
        prompt = (f"{RL_PROMPT_START}{self.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}┌─{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}"
                 f"[{RL_PROMPT_START}{self.COLOR_BRIGHT_GREEN}{RL_PROMPT_END}{self.username}"
                 f"{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}"
                 f"{RL_PROMPT_START}{self.COLOR_BRIGHT_WHITE}{RL_PROMPT_END}@{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}"
                 f"{RL_PROMPT_START}{self.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}ZDTT{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END} "
                 f"{RL_PROMPT_START}{self.COLOR_BRIGHT_BLUE}{RL_PROMPT_END}{display_path}"
                 f"{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}]"
                 f"{RL_PROMPT_START}{self.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}─{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}\n"
                 f"{RL_PROMPT_START}{self.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}└─{RL_PROMPT_START}{self.COLOR_BRIGHT_MAGENTA}{RL_PROMPT_END}➜{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END} ")
        return prompt
    
    def cmd_help(self, args):
        """Display available commands with enhanced formatting"""
        print()
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}╔═══════════════════════════════════════════════════════════╗{self.COLOR_RESET}")
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}║{self.COLOR_RESET}  {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}ZDTT Terminal Commands{self.COLOR_RESET}                                    {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}║{self.COLOR_RESET}")
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}╚═══════════════════════════════════════════════════════════╝{self.COLOR_RESET}")
        print()
        print(f"{self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}Core Commands:{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_GREEN}help{self.COLOR_RESET}                 - Display this help message")
        print(f"  {self.COLOR_BRIGHT_GREEN}clear{self.COLOR_RESET}                - Clear the screen")
        print(f"  {self.COLOR_BRIGHT_GREEN}echo{self.COLOR_RESET} <message>       - Echo a message")
        print(f"  {self.COLOR_BRIGHT_GREEN}about{self.COLOR_RESET}                - About ZDTT Terminal")
        print(f"  {self.COLOR_BRIGHT_GREEN}history{self.COLOR_RESET}              - Show command history")
        print(f"  {self.COLOR_BRIGHT_GREEN}plugins{self.COLOR_RESET} [reload]     - List or reload plugins")
        print(f"  {self.COLOR_BRIGHT_GREEN}alias{self.COLOR_RESET} [name=cmd]     - Create or display command aliases")
        print(f"  {self.COLOR_BRIGHT_GREEN}unalias{self.COLOR_RESET} <name>       - Remove an alias")
        print(f"  {self.COLOR_BRIGHT_GREEN}zps{self.COLOR_RESET} install <url>    - Install plugin from URL")
        print(f"  {self.COLOR_BRIGHT_GREEN}time{self.COLOR_RESET} [options]       - Display date/time (MM/DD/YY 12h default)")
        print(f"  {self.COLOR_BRIGHT_GREEN}statusbar{self.COLOR_RESET} color <name> - Change status bar highlight color")
        print(f"  {self.COLOR_BRIGHT_GREEN}update{self.COLOR_RESET}               - Run the ZDTT updater helper")
        print(f"  {self.COLOR_BRIGHT_GREEN}exit{self.COLOR_RESET}                 - Exit ZDTT (return to shell)")
        print(f"  {self.COLOR_BRIGHT_GREEN}quit{self.COLOR_RESET}                 - Quit and close terminal window")
        print()
        print(f"{self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}File System Commands:{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_GREEN}ls{self.COLOR_RESET} [options]         - List directory contents")
        print(f"  {self.COLOR_BRIGHT_GREEN}pwd{self.COLOR_RESET}                  - Print working directory")
        print(f"  {self.COLOR_BRIGHT_GREEN}cd{self.COLOR_RESET} <directory>       - Change directory")
        print(f"  {self.COLOR_BRIGHT_GREEN}cat{self.COLOR_RESET} <file>           - Display file contents")
        print(f"  {self.COLOR_BRIGHT_GREEN}mkdir{self.COLOR_RESET} <directory>    - Create directory")
        print(f"  {self.COLOR_BRIGHT_GREEN}touch{self.COLOR_RESET} <file>         - Create empty file")
        print(f"  {self.COLOR_BRIGHT_GREEN}rm{self.COLOR_RESET} [-rf] <file>      - Remove file/directory (prompts without -f)")
        print(f"  {self.COLOR_BRIGHT_GREEN}mv{self.COLOR_RESET} <src> <dest>      - Move/rename file")
        print(f"  {self.COLOR_BRIGHT_GREEN}cp{self.COLOR_RESET} [-r] <src> <dest> - Copy file")
        print(f"  {self.COLOR_BRIGHT_GREEN}grep{self.COLOR_RESET} <pattern> <file> - Search for pattern in file")
        print()
        print(f"{self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}System Commands:{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_GREEN}whoami{self.COLOR_RESET}               - Display current user")
        print(f"  {self.COLOR_BRIGHT_GREEN}date{self.COLOR_RESET}                 - Display current date/time")
        print(f"  {self.COLOR_BRIGHT_GREEN}uname{self.COLOR_RESET} [options]      - Display system information")
        print(f"  {self.COLOR_BRIGHT_GREEN}nano{self.COLOR_RESET} <file>          - Edit file with nano")
        print(f"  {self.COLOR_BRIGHT_GREEN}sysfetch{self.COLOR_RESET}             - Display system info (prefers distro tools)")
        print()
        print(f"{self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}Python Commands:{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_GREEN}python{self.COLOR_RESET} [args]        - Run Python interpreter")
        print(f"  {self.COLOR_BRIGHT_GREEN}python3{self.COLOR_RESET} [args]       - Run Python 3 interpreter")
        print(f"  {self.COLOR_BRIGHT_GREEN}pip{self.COLOR_RESET} [args]           - Run pip package manager")
        print(f"  {self.COLOR_BRIGHT_GREEN}pip3{self.COLOR_RESET} [args]          - Run pip3 package manager")
        print()
        print(f"{self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}Features:{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_YELLOW}↑/↓ arrows{self.COLOR_RESET}           - Navigate command history")
        print(f"  {self.COLOR_BRIGHT_YELLOW}Tab{self.COLOR_RESET}                  - Auto-complete commands/files")
        print(f"  {self.COLOR_BRIGHT_YELLOW}Auto shell fallback{self.COLOR_RESET} - Unknown commands run in system shell")
        print(f"                         {self.COLOR_DIM}Example: htop (auto-runs in shell){self.COLOR_RESET}")
        print()
    
    def cmd_clear(self, args):
        """Clear the terminal screen"""
        os.system('clear' if os.name != 'nt' else 'cls')
        self._set_scroll_region()
        self._render_status_bar()
        self.display_banner()
    
    def cmd_exit(self, args):
        """Exit ZDTT Terminal (returns to parent shell)"""
        print("Goodbye!")
        os.system('clear' if os.name != 'nt' else 'cls')
        self.running = False
    
    def cmd_quit(self, args):
        """Quit and close the terminal window completely"""
        print("Closing terminal window...")
        # Exit the Python process with code 0
        # This will return control to the parent shell, which will then exit
        sys.exit(0)
    
    def cmd_about(self, args):
        """Display information about ZDTT Terminal with enhanced formatting"""
        print()
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}╔═══════════════════════════════════════════════════════════╗{self.COLOR_RESET}")
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}║{self.COLOR_RESET}  {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}About ZDTT Terminal{self.COLOR_RESET}                                        {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}║{self.COLOR_RESET}")
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}╚═══════════════════════════════════════════════════════════╝{self.COLOR_RESET}")
        print()
        print(f"  {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Version:{self.COLOR_RESET} {self.COLOR_BRIGHT_WHITE}v{self.version}{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Description:{self.COLOR_RESET} A custom terminal interface for Debian-based and Arch Linux systems")
        print()
        
        # Show distribution status with colors
        print(f"  {self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}System Status:{self.COLOR_RESET}")
        if self.is_debian:
            print(f"    {self.COLOR_BRIGHT_GREEN}✓{self.COLOR_RESET} Debian-based system {self.COLOR_BRIGHT_GREEN}(fully supported){self.COLOR_RESET}")
        elif self.is_arch:
            print(f"    {self.COLOR_BRIGHT_GREEN}✓{self.COLOR_RESET} Arch Linux {self.COLOR_BRIGHT_GREEN}(fully supported){self.COLOR_RESET}")
        else:
            print(f"    {self.COLOR_WARNING}⚠{self.COLOR_RESET} Unsupported system {self.COLOR_WARNING}(limited support){self.COLOR_RESET}")
        
        print()
        print(f"  {self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}Features:{self.COLOR_RESET}")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Automatic update checking on startup")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Command history with ↑/↓ navigation (1000 commands)")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Tab completion for commands and files")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Command aliases (alias g=git)")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Flexible time/date display with multiple formats")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Colorized prompt with enhanced styling")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Smart banner (auto-hides on small terminals)")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Plugin system with ZPS package manager")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Plugin hot-reload (plugins reload)")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Safe rm with confirmation prompts")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Custom banner support (~/.zdtt/banner.txt)")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Native command support")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} System command execution via -oszdtt flag")
        print(f"    {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} Clean, premium interface")
        print()
        print(f"  {self.COLOR_BRIGHT_MAGENTA}{self.COLOR_BOLD}Configuration:{self.COLOR_RESET}")
        print(f"    {self.COLOR_DIM}•{self.COLOR_RESET} ZDTT directory: {self.COLOR_BRIGHT_CYAN}{self.zdtt_dir}{self.COLOR_RESET}")
        print(f"    {self.COLOR_DIM}•{self.COLOR_RESET} Aliases: {self.COLOR_BRIGHT_CYAN}{self.aliases_file}{self.COLOR_RESET}")
        print(f"    {self.COLOR_DIM}•{self.COLOR_RESET} Custom banner: {self.COLOR_BRIGHT_CYAN}{self.banner_file}{self.COLOR_RESET}")
        print(f"    {self.COLOR_DIM}•{self.COLOR_RESET} Plugin errors: {self.COLOR_BRIGHT_CYAN}{self.log_file}{self.COLOR_RESET}")
        print()
    
    def cmd_history(self, args):
        """Display command history with enhanced formatting"""
        history_length = readline.get_current_history_length()
        
        if history_length == 0:
            print(f"{self.COLOR_WARNING}No history available{self.COLOR_RESET}")
            return
        
        # Show last 50 commands by default
        limit = 50
        if args and args[0].isdigit():
            limit = int(args[0])
        
        start = max(1, history_length - limit + 1)
        
        print()
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Command History:{self.COLOR_RESET} (showing {limit} of {history_length} commands)")
        print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
        for i in range(start, history_length + 1):
            cmd = readline.get_history_item(i)
            if cmd:
                print(f"{self.COLOR_BRIGHT_BLACK}{i:4d}{self.COLOR_RESET}  {self.COLOR_BRIGHT_CYAN}{cmd}{self.COLOR_RESET}")
        print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
        print()
    
    def cmd_plugins(self, args):
        """List or reload plugins"""
        # Check for reload subcommand
        if args and args[0] == 'reload':
            print(f"{self.COLOR_BRIGHT_CYAN}Reloading plugins...{self.COLOR_RESET}")
            # Remove plugin commands and reload aliases to avoid conflicts
            self.unload_plugin_commands()
            self.aliases.clear()
            self.load_aliases()
            
            # Reload plugins
            self.load_plugins()
            print(f"{self.COLOR_BRIGHT_GREEN}✓ Plugins reloaded successfully!{self.COLOR_RESET}")
            print()
            return
        
        # List plugins
        plugin_files = glob.glob(os.path.join(self.plugin_dir, "*.py"))
        
        if not plugin_files:
            print()
            print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Plugins:{self.COLOR_RESET}")
            print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
            print(f"{self.COLOR_WARNING}No plugins installed.{self.COLOR_RESET}")
            print()
            print(f"Plugin directory: {self.COLOR_BRIGHT_CYAN}{self.plugin_dir}{self.COLOR_RESET}")
            print()
            print(f"{self.COLOR_DIM}To create a plugin, create a .py file with a register_commands() function{self.COLOR_RESET}")
            print(f"{self.COLOR_DIM}that returns a dictionary of command names to functions.{self.COLOR_RESET}")
            print()
            print(f"Or use: {self.COLOR_BRIGHT_GREEN}zps install <url>{self.COLOR_RESET} to install from a URL")
            print()
            return
        
        print()
        print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Loaded Plugins:{self.COLOR_RESET} {self.COLOR_BRIGHT_GREEN}({len(plugin_files)}){self.COLOR_RESET}")
        print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
        for plugin_file in plugin_files:
            plugin_name = os.path.basename(plugin_file)[:-3]
            print(f"  {self.COLOR_BRIGHT_GREEN}•{self.COLOR_RESET} {self.COLOR_BRIGHT_CYAN}{plugin_name}{self.COLOR_RESET}")
        print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
        print()
        print(f"Plugin directory: {self.COLOR_BRIGHT_CYAN}{self.plugin_dir}{self.COLOR_RESET}")
        print(f"Error log: {self.COLOR_BRIGHT_CYAN}{self.log_file}{self.COLOR_RESET}")
        print()
        print(f"{self.COLOR_BRIGHT_MAGENTA}Commands:{self.COLOR_RESET}")
        print(f"  {self.COLOR_BRIGHT_GREEN}plugins reload{self.COLOR_RESET}  - Reload all plugins without restarting")
        print()
    
    def cmd_alias(self, args):
        """Create or display command aliases"""
        if not args:
            # Display all aliases
            if not self.aliases:
                print()
                print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Aliases:{self.COLOR_RESET}")
                print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
                print(f"{self.COLOR_WARNING}No aliases defined.{self.COLOR_RESET}")
                print()
                print(f"Usage: {self.COLOR_BRIGHT_GREEN}alias name=command{self.COLOR_RESET}")
                print(f"Example: {self.COLOR_BRIGHT_GREEN}alias g=git{self.COLOR_RESET}")
                print()
            else:
                print()
                print(f"{self.COLOR_BRIGHT_CYAN}{self.COLOR_BOLD}Defined Aliases:{self.COLOR_RESET} {self.COLOR_BRIGHT_GREEN}({len(self.aliases)}){self.COLOR_RESET}")
                print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
                for name, command in sorted(self.aliases.items()):
                    print(f"  {self.COLOR_BRIGHT_GREEN}{name}{self.COLOR_RESET}={self.COLOR_BRIGHT_CYAN}{command}{self.COLOR_RESET}")
                print(f"{self.COLOR_DIM}{'─' * 60}{self.COLOR_RESET}")
                print()
            return
        
        # Parse alias definition
        alias_def = ' '.join(args)
        
        if '=' not in alias_def:
            # Display specific alias
            alias_name = args[0]
            if alias_name in self.aliases:
                print(f"{alias_name}={self.aliases[alias_name]}")
            else:
                print(f"alias: {alias_name}: not found")
            return
        
        # Create new alias
        name, command = alias_def.split('=', 1)
        name = name.strip()
        command = command.strip()
        
        if not name or not command:
            print("alias: invalid format")
            print("Usage: alias name=command")
            return
        
        # Check if alias would shadow a built-in command
        if name in self.commands:
            print(f"Warning: '{name}' is a built-in command. Alias will take precedence.")
        
        self.aliases[name] = command
        self.save_aliases()
        print(f"Alias created: {name}={command}")
    
    def cmd_unalias(self, args):
        """Remove command aliases"""
        if not args:
            print("unalias: missing alias name")
            print("Usage: unalias name")
            return
        
        name = args[0]
        if name in self.aliases:
            del self.aliases[name]
            self.save_aliases()
            print(f"Alias removed: {name}")
        else:
            print(f"unalias: {name}: not found")
    
    def cmd_zps(self, args):
        """ZDTT Package System - Install plugins from URLs"""
        if not args:
            print("\nZDTT Package System (ZPS)")
            print("\nUsage:")
            print("  zps install <url>    - Install plugin from URL")
            print("  zps list             - List installed plugins (same as 'plugins')")
            print("\nExamples:")
            print("  zps install https://plugins.zane.org/example_plugin.py")
            print("  zps install https://raw.githubusercontent.com/user/repo/plugin.py")
            print()
            return
        
        subcommand = args[0]
        
        if subcommand == 'list':
            self.cmd_plugins([])
            return
        
        if subcommand == 'install':
            if len(args) < 2:
                print("zps install: missing URL")
                print("Usage: zps install <url>")
                return
            
            url = args[1]
            
            # Extract filename from URL
            filename = url.split('/')[-1]
            
            # Validate it's a .py file
            if not filename.endswith('.py'):
                print(f"{self.COLOR_ERROR}Error: '{filename}' is not a Python file{self.COLOR_RESET}")
                print("Plugin URLs must end with .py")
                return
            
            # Create plugins directory if it doesn't exist
            os.makedirs(self.plugin_dir, exist_ok=True)
            
            target_path = os.path.join(self.plugin_dir, filename)
            
            # Check if plugin already exists
            if os.path.exists(target_path):
                response = input(f"Plugin '{filename}' already exists. Overwrite? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("Installation cancelled.")
                    return
            
            print(f"Downloading {filename}...")
            
            try:
                # Download the file
                with urllib.request.urlopen(url) as response:
                    plugin_content = response.read()
                
                # Write to plugin directory
                with open(target_path, 'wb') as f:
                    f.write(plugin_content)
                
                print(f"{self.COLOR_BRIGHT_GREEN}✓ Plugin '{filename}' installed successfully!{self.COLOR_RESET}")
                print(f"  Location: {target_path}")
                print()
                print("To use the plugin:")
                print("  1. Type 'plugins reload' to load it now")
                print("  2. Or restart ZDTT")
                print()
                
            except urllib.error.HTTPError as e:
                print(f"{self.COLOR_ERROR}Error: Failed to download plugin (HTTP {e.code}){self.COLOR_RESET}")
                print(f"URL: {url}")
            except urllib.error.URLError as e:
                print(f"{self.COLOR_ERROR}Error: Failed to connect to server{self.COLOR_RESET}")
                print(f"Reason: {e.reason}")
            except Exception as e:
                print(f"{self.COLOR_ERROR}Error: {e}{self.COLOR_RESET}")
            
            return
        
        print(f"zps: unknown subcommand '{subcommand}'")
        print("Try: zps install <url>")
    
    def cmd_time(self, args):
        """Display current date and time with various formats"""
        now = datetime.now()
        
        # Parse arguments
        use_24h = False
        custom_format = None
        
        for arg in args:
            if arg in ['--24h', '-24', '24h']:
                use_24h = True
            elif arg in ['--12h', '-12', '12h']:
                use_24h = False
            elif arg.startswith('--format='):
                custom_format = arg.split('=', 1)[1]
            elif arg in ['--help', '-h']:
                print("\nTime Command - Display current date and time")
                print("\nUsage:")
                print("  time              - Default format (MM/DD/YY 12h)")
                print("  time --24h        - Use 24-hour format")
                print("  time --12h        - Use 12-hour format (default)")
                print("  time --format=... - Custom format string")
                print("\nPre-defined formats:")
                print("  time iso          - ISO 8601 format")
                print("  time full         - Full date and time")
                print("  time date         - Date only")
                print("  time clock        - Time only")
                print("  time unix         - Unix timestamp")
                print("\nCustom format codes:")
                print("  %Y - Year (4 digit)    %m - Month (01-12)")
                print("  %d - Day (01-31)       %H - Hour (00-23)")
                print("  %I - Hour (01-12)      %M - Minute (00-59)")
                print("  %S - Second (00-59)    %p - AM/PM")
                print("  %A - Weekday name      %B - Month name")
                print("\nExample:")
                print("  time --format='%Y-%m-%d %H:%M:%S'")
                print()
                return
            elif arg == 'iso':
                custom_format = '%Y-%m-%d %H:%M:%S'
                use_24h = True
            elif arg == 'full':
                custom_format = '%A, %B %d, %Y at %I:%M:%S %p'
            elif arg == 'date':
                print(now.strftime('%m/%d/%y'))
                return
            elif arg == 'clock':
                if use_24h:
                    print(now.strftime('%H:%M:%S'))
                else:
                    print(now.strftime('%I:%M:%S %p'))
                return
            elif arg == 'unix':
                print(int(time_module.time()))
                return
        
        # Apply custom format if specified
        if custom_format:
            try:
                print(now.strftime(custom_format))
            except Exception as e:
                print(f"{self.COLOR_ERROR}Error: Invalid format string - {e}{self.COLOR_RESET}")
            return
        
        # Default format: MM/DD/YY with time
        date_str = now.strftime('%m/%d/%y')
        
        if use_24h:
            time_str = now.strftime('%H:%M:%S')
        else:
            time_str = now.strftime('%I:%M:%S %p')
        
        print(f"{date_str} {time_str}")
    
    def cmd_statusbar(self, args):
        """Configure the status bar appearance."""
        if not args:
            print(f"Status bar color: {self.status_bar_color}")
            print("Usage: statusbar color <color>")
            print(f"Available colors: {', '.join(sorted(STATUS_BAR_COLORS.keys()))}")
            return
        
        subcommand = args[0].lower()
        if subcommand != 'color':
            print("Unknown statusbar option. Usage: statusbar color <color>")
            return
        
        if len(args) < 2:
            print("Missing color. Usage: statusbar color <color>")
            print(f"Available colors: {', '.join(sorted(STATUS_BAR_COLORS.keys()))}")
            return
        
        color = args[1].lower()
        if color not in STATUS_BAR_COLORS:
            print(f"Unsupported color '{color}'.")
            print(f"Available colors: {', '.join(sorted(STATUS_BAR_COLORS.keys()))}")
            return
        
        self.status_bar_color = color
        self.save_preferences()
        self._render_status_bar()
        print(f"{self.COLOR_BRIGHT_GREEN}✓{self.COLOR_RESET} Status bar color updated to {self.COLOR_BRIGHT_CYAN}{color}{self.COLOR_RESET}.")
    
    def cmd_echo(self, args):
        """Echo the provided arguments"""
        if args:
            print(' '.join(args))
        else:
            print()
    
    # File System Commands
    
    def cmd_ls(self, args):
        """List directory contents"""
        cmd = ['ls', '--color=auto'] + args
        subprocess.run(cmd)
    
    def cmd_pwd(self, args):
        """Print working directory"""
        print(os.getcwd())
    
    def cmd_cd(self, args):
        """Change directory"""
        if not args:
            # Go to home directory
            target = os.path.expanduser("~")
        else:
            target = args[0]
        
        try:
            # Expand ~ and handle relative paths
            target = os.path.expanduser(target)
            os.chdir(target)
            self.current_dir = os.getcwd()
        except FileNotFoundError:
            print(f"cd: {target}: No such file or directory")
        except NotADirectoryError:
            print(f"cd: {target}: Not a directory")
        except PermissionError:
            print(f"cd: {target}: Permission denied")
    
    def cmd_cat(self, args):
        """Display file contents"""
        if not args:
            print("cat: missing file operand")
            return
        
        for filename in args:
            try:
                with open(filename, 'r') as f:
                    print(f.read(), end='')
            except FileNotFoundError:
                print(f"cat: {filename}: No such file or directory")
            except PermissionError:
                print(f"cat: {filename}: Permission denied")
            except IsADirectoryError:
                print(f"cat: {filename}: Is a directory")
    
    def cmd_mkdir(self, args):
        """Create directory"""
        if not args:
            print("mkdir: missing operand")
            return
        
        for directory in args:
            try:
                os.makedirs(directory, exist_ok=False)
            except FileExistsError:
                print(f"mkdir: cannot create directory '{directory}': File exists")
            except PermissionError:
                print(f"mkdir: cannot create directory '{directory}': Permission denied")
    
    def cmd_touch(self, args):
        """Create empty file"""
        if not args:
            print("touch: missing file operand")
            return
        
        for filename in args:
            try:
                open(filename, 'a').close()
            except PermissionError:
                print(f"touch: cannot touch '{filename}': Permission denied")
    
    def cmd_rm(self, args):
        """Remove file or directory"""
        if not args:
            print("rm: missing operand")
            return
        
        # Separate flags from paths
        flags = [arg for arg in args if arg.startswith('-')]
        paths = [arg for arg in args if not arg.startswith('-')]
        
        if not paths:
            print("rm: missing operand")
            return
        
        # Check for recursive flag
        recursive = '-r' in flags or '-rf' in flags or '-fr' in flags
        force = '-f' in flags or '-rf' in flags or '-fr' in flags
        
        for path in paths:
            try:
                if os.path.islink(path):
                    os.unlink(path)
                elif os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    if recursive:
                        # Confirm before removing directory unless -f flag
                        if not force:
                            # Get absolute path for display
                            abs_path = os.path.abspath(path)
                            try:
                                # Count items in directory
                                item_count = sum(len(files) + len(dirs) for _, dirs, files in os.walk(path))
                                print(f"rm: remove directory '{abs_path}' and its {item_count} items?")
                            except:
                                print(f"rm: remove directory '{abs_path}'?")
                            
                            response = input("Type 'yes' to confirm: ").strip().lower()
                            if response != 'yes':
                                print("rm: operation cancelled")
                                continue
                        
                        shutil.rmtree(path)
                    else:
                        print(f"rm: cannot remove '{path}': Is a directory")
                        print("rm: use 'rm -r' to remove directories")
                else:
                    if not force:
                        print(f"rm: cannot remove '{path}': No such file or directory")
            except PermissionError:
                if not force:
                    print(f"rm: cannot remove '{path}': Permission denied")
            except Exception as e:
                if not force:
                    print(f"rm: error removing '{path}': {e}")
    
    def cmd_mv(self, args):
        """Move/rename file"""
        if len(args) < 2:
            print("mv: missing file operand")
            return
        
        src = args[0]
        dest = args[1]
        
        try:
            shutil.move(src, dest)
        except FileNotFoundError:
            print(f"mv: cannot stat '{src}': No such file or directory")
        except PermissionError:
            print(f"mv: cannot move '{src}': Permission denied")
    
    def cmd_cp(self, args):
        """Copy file"""
        if len(args) < 2:
            print("cp: missing file operand")
            return
        
        # Separate flags from paths
        flags = [arg for arg in args if arg.startswith('-')]
        paths = [arg for arg in args if not arg.startswith('-')]
        
        if len(paths) < 2:
            print("cp: missing destination file operand")
            return
        
        src = paths[0]
        dest = paths[1]
        
        # Check for recursive flag
        recursive = '-r' in flags or '-R' in flags
        
        try:
            if os.path.isfile(src):
                shutil.copy2(src, dest)
            elif os.path.isdir(src):
                if recursive:
                    shutil.copytree(src, dest)
                else:
                    print(f"cp: -r not specified; omitting directory '{src}'")
            else:
                print(f"cp: cannot stat '{src}': No such file or directory")
        except FileNotFoundError:
            print(f"cp: cannot stat '{src}': No such file or directory")
        except PermissionError:
            print(f"cp: cannot create '{dest}': Permission denied")
        except FileExistsError:
            print(f"cp: cannot create directory '{dest}': File exists")
    
    def cmd_grep(self, args):
        """Search for pattern in file"""
        if len(args) < 2:
            print("grep: missing pattern or file")
            return
        
        cmd = ['grep', '--color=auto'] + args
        subprocess.run(cmd)
    
    # System Commands
    
    def cmd_whoami(self, args):
        """Display current user"""
        print(self.username)
    
    def cmd_date(self, args):
        """Display current date/time"""
        subprocess.run(['date'] + args)
    
    def cmd_uname(self, args):
        """Display system information"""
        subprocess.run(['uname'] + args)
    
    def cmd_nano(self, args):
        """Edit file with nano"""
        if not args:
            print("nano: missing file operand")
            return
        
        subprocess.run(['nano'] + args)
    
    def cmd_sysfetch(self, args):
        """Display system info using distro-preferred fetch tool."""
        def _find_tool_binary(tool_name):
            candidate = shutil.which(tool_name)
            if candidate:
                return candidate
            for path in (
                f"/usr/bin/{tool_name}",
                f"/usr/local/bin/{tool_name}",
                os.path.expanduser(f"~/.local/bin/{tool_name}"),
            ):
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path
            return None

        def _build_install_command(tool_name):
            manual_hint = None
            base_cmd = None
            if tool_name == 'fastfetch' and self.is_arch:
                base_cmd = ['pacman', '-S', '--noconfirm', 'fastfetch']
                manual_hint = "sudo pacman -S fastfetch"
            elif tool_name == 'neofetch' and self.is_debian:
                base_cmd = ['apt-get', 'install', '-y', 'neofetch']
                manual_hint = "sudo apt-get install neofetch"
            else:
                return None, manual_hint

            geteuid = getattr(os, 'geteuid', None)
            is_root = geteuid is not None and geteuid() == 0
            sudo_path = shutil.which('sudo')

            if is_root:
                return base_cmd, manual_hint
            if sudo_path:
                return [sudo_path] + base_cmd, manual_hint
            return None, manual_hint

        tool_name = 'fastfetch' if self.is_arch else 'neofetch' if self.is_debian else None
        if not tool_name:
            print("sysfetch currently supports Debian-based or Arch-based systems only.")
            return

        tool_bin = _find_tool_binary(tool_name)
        if not tool_bin:
            install_cmd, manual_hint = _build_install_command(tool_name)
            if install_cmd:
                print(f"{tool_name} is not installed. Installing...")
                print()
                try:
                    subprocess.run(install_cmd, check=True)
                    print()
                    print(f"{tool_name} installed successfully!")
                    print()
                except subprocess.CalledProcessError:
                    print(f"Failed to install {tool_name}")
                    if manual_hint:
                        print(f"Try manually: {manual_hint}")
                    else:
                        print("Please install the tool via your package manager.")
            elif manual_hint:
                print(manual_hint)
            tool_bin = _find_tool_binary(tool_name)

        if not tool_bin:
            print(f"Unable to run {tool_name}. Install it manually and rerun sysfetch.")
            return

        subprocess.run([tool_bin] + args)
        print(f"\n(sysfetch used {tool_name})\n")
    
    # Python Commands
    
    def cmd_python(self, args):
        """Run python command"""
        subprocess.run(['python'] + args)
    
    def cmd_python3(self, args):
        """Run python3 command"""
        subprocess.run(['python3'] + args)

    def cmd_pip(self, args):
        """Run pip command"""
        if shutil.which('pip'):
            subprocess.run(['pip'] + args)
        else:
            print("pip: command not found")
            print("Try installing with: sudo apt-get install python3-pip")
    
    def cmd_pip3(self, args):
        """Run pip3 command"""
        if shutil.which('pip3'):
            subprocess.run(['pip3'] + args)
        else:
            print("pip3: command not found")
            print("Try installing with: sudo apt-get install python3-pip")

    def cmd_update(self, args):
        """Trigger the external updater shipping with ZDTT."""
        zdtt_wrapper = shutil.which('zdtt')
        installer_script = os.path.join(
            os.path.expanduser("~/.local/share/zdtt"),
            'install.sh'
        )

        if zdtt_wrapper:
            subprocess.run([zdtt_wrapper, 'update'] + args)
            return

        if os.path.isfile(installer_script):
            subprocess.run(['bash', installer_script, 'update'] + args)
            return

        print("Unable to locate the ZDTT updater.")
        print("Re-run the installer script or use 'zdtt update' from your shell if available.")
    
    def _execute_system_command(self, command):
        """Execute a system command with real-time I/O streaming."""
        # Temporarily disable status bar updates during command execution
        status_bar_was_running = self.status_bar_thread and self.status_bar_thread.is_alive()
        
        try:
            # Start the process with direct stdin/stdout/stderr
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                stdin=sys.stdin,  # Direct stdin passthrough
                bufsize=1,  # Line buffered
                text=True,
                cwd=self.current_dir
            )
            
            # Buffer for early output detection
            early_output = []
            start_time = time_module.time()
            check_timeout = 0.1  # 0.1 seconds
            hide_output = False
            output_buffer = []
            
            # Read output in real-time
            try:
                while True:
                    # Read character by character for early detection
                    char = process.stdout.read(1)
                    if not char:
                        if process.poll() is not None:
                            break
                        time_module.sleep(0.01)
                        continue
                    
                    # Check for "command not found" in first 0.1 seconds
                    if time_module.time() - start_time < check_timeout:
                        early_output.append(char)
                        combined = ''.join(early_output).lower()
                        if 'command not found' in combined or 'not found:' in combined:
                            hide_output = True
                            # Consume remaining output silently
                            while process.poll() is None:
                                process.stdout.read(1)
                            break
                    
                    # Buffer output
                    output_buffer.append(char)
                    
                    # If we have a complete line or enough chars, flush
                    if char == '\n' or len(output_buffer) >= 1024:
                        if not hide_output:
                            sys.stdout.write(''.join(output_buffer))
                            sys.stdout.flush()
                        output_buffer.clear()
                
                # Flush remaining buffer
                if output_buffer and not hide_output:
                    sys.stdout.write(''.join(output_buffer))
                    sys.stdout.flush()
                
                # Wait for process to finish
                process.wait()
                
            except BrokenPipeError:
                # Process closed stdout
                pass
            
        except KeyboardInterrupt:
            # Handle Ctrl+C
            try:
                if 'process' in locals():
                    process.terminate()
                    process.wait(timeout=1)
            except Exception:
                try:
                    if 'process' in locals():
                        process.kill()
                except Exception:
                    pass
            print("\n^C")
        except Exception as e:
            if not hide_output:
                print(f"{self.COLOR_ERROR}Error executing command: {e}{self.COLOR_RESET}")
        finally:
            # Restore status bar if it was running
            if status_bar_was_running:
                self._render_status_bar()

    def execute_command(self, command_line):
        """Parse and execute a command"""
        if not command_line.strip():
            return
        
        # Expand aliases first
        command_line = self.expand_aliases(command_line)
        
        # Check for -oszdtt flag (Outside ZDTT) - still supported for explicit shell execution
        if '-oszdtt' in command_line:
            # Remove the -oszdtt flag and execute as system command
            system_command = command_line.replace('-oszdtt', '').strip()
            if system_command:
                self._execute_system_command(system_command)
            else:
                print("No command specified with -oszdtt flag")
            return
        
        try:
            parts = shlex.split(command_line)
        except ValueError as exc:
            print(f"parse error: {exc}")
            return

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            # Command not found in ZDTT - automatically run in shell
            self._execute_system_command(command_line)
    
    def run(self):
        """Main terminal loop"""
        # Setup signal handler for terminal resize (SIGWINCH)
        if sys.platform != 'win32':
            try:
                signal.signal(signal.SIGWINCH, self._handle_resize)
            except (AttributeError, ValueError):
                # SIGWINCH not available on this platform
                pass
        
        # Clear screen and display banner
        os.system('clear' if os.name != 'nt' else 'cls')
        self.initialize_status_bar()
        self.display_banner()
        
        # Main command loop
        try:
            while self.running:
                try:
                    command = input(self.get_prompt())
                    self.execute_command(command)
                except KeyboardInterrupt:
                    print("\nUse 'exit' to return to shell, or 'quit' to close the window.")
                except EOFError:
                    print("\nGoodbye!")
                    break
        finally:
            self.shutdown_status_bar()


def main():
    # Check system compatibility
    distro = check_system_compatibility()
    
    terminal = ZDTTTerminal(distro=distro)
    terminal.run()


if __name__ == "__main__":
    main()
