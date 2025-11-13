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


def check_system_compatibility():
    """Detect supported distributions and warn when unsupported"""
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
        return 'other'
    
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
        
        # Setup logging for plugins
        self.setup_logging()
        
        # Load user aliases
        self.aliases = {}
        self.load_aliases()
        
        # Read version from version.txt
        self.version = self.read_version()
        
        # Load user preferences (status bar color, etc.)
        self.load_preferences()
        
        # ANSI color codes
        self.COLOR_RESET = '\033[0m'
        self.COLOR_GREEN = '\033[92m'
        self.COLOR_BLUE = '\033[94m'
        self.COLOR_CYAN = '\033[96m'
        self.COLOR_BOLD = '\033[1m'
        
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
            # System commands
            'ls': self.cmd_ls,
            'pwd': self.cmd_pwd,
            'cd': self.cmd_cd,
            'cat': self.cmd_cat,
            'nano': self.cmd_nano,
            'fastfetch': self.cmd_fastfetch,
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
        
        # Check for updates (non-blocking)
        self.check_for_updates()
    
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
        """Load user preferences such as status bar color."""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            self.status_bar_color = data.get('status_bar_color', self.status_bar_color)
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
        
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def check_for_updates(self):
        """Check if a new version is available"""
        try:
            # Get remote version
            url = "https://zdtt-sources.zane.org/version.txt"
            with urllib.request.urlopen(url, timeout=2) as response:
                remote_version = response.read().decode('utf-8').strip()
            
            # Compare versions
            if remote_version != self.version:
                print()
                print(f"🔔 Update available! Current: {self.version} → Latest: {remote_version}")
                print("   Run 'zdtt update' to update")
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
        bar_text = self._build_status_bar_text()
        try:
            sys.stdout.write("\033[s")          # Save cursor position
            sys.stdout.write("\033[1;1H")       # Move to first row
            sys.stdout.write("\033[2K")         # Clear the line
            sys.stdout.write(bar_text)
            sys.stdout.write(self.COLOR_RESET)
            sys.stdout.write("\033[u")          # Restore cursor
            sys.stdout.flush()
        except Exception:
            print(bar_text)
    
    def _build_status_bar_text(self):
        left_text = "ZDTT by ZaneDev"
        time_str = datetime.now().strftime("%I:%M:%p").lower()
        try:
            term_size = shutil.get_terminal_size()
            width = max(term_size.columns, len(left_text) + len(time_str) + 4)
        except Exception:
            width = len(left_text) + len(time_str) + 4
        
        padding = max(width - len(left_text) - len(time_str) - 2, 1)
        bar_plain = f" {left_text}{' ' * padding}{time_str} "
        if len(bar_plain) < width:
            bar_plain = bar_plain.ljust(width)
        else:
            bar_plain = bar_plain[:width]
        bg_code, fg_code = STATUS_BAR_COLORS.get(self.status_bar_color, ('44', '97'))
        return f"\033[{bg_code}m\033[{fg_code}m{bar_plain}"
    
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
            print(f"⚠ {failed_count} plugin(s) failed to load. Check ~/.zdtt/plugin_errors.log")
    
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
            print(f"Error: Failed to save aliases: {e}")
    
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
        """Return the custom prompt string with colors"""
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
        
        # Create colorized prompt with readline-safe escape codes
        # [username in green @ ZDTT path in blue]=>
        prompt = (f"[{RL_PROMPT_START}{self.COLOR_GREEN}{RL_PROMPT_END}{self.username}"
                 f"{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}"
                 f"@{RL_PROMPT_START}{self.COLOR_CYAN}{RL_PROMPT_END}ZDTT{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END} "
                 f"{RL_PROMPT_START}{self.COLOR_BLUE}{RL_PROMPT_END}{display_path}"
                 f"{RL_PROMPT_START}{self.COLOR_RESET}{RL_PROMPT_END}]=> ")
        return prompt
    
    def cmd_help(self, args):
        """Display available commands"""
        print("\nZDTT Terminal Commands:")
        print("  help                 - Display this help message")
        print("  clear                - Clear the screen")
        print("  echo <message>       - Echo a message")
        print("  about                - About ZDTT Terminal")
        print("  history              - Show command history")
        print("  plugins [reload]     - List or reload plugins")
        print("  alias [name=cmd]     - Create or display command aliases")
        print("  unalias <name>       - Remove an alias")
        print("  zps install <url>    - Install plugin from URL")
        print("  time [options]       - Display date/time (MM/DD/YY 12h default)")
        print("  statusbar color <name> - Change status bar highlight color")
        print("  exit                 - Exit ZDTT (return to shell)")
        print("  quit                 - Quit and close terminal window")
        print()
        print("File System Commands:")
        print("  ls [options]         - List directory contents")
        print("  pwd                  - Print working directory")
        print("  cd <directory>       - Change directory")
        print("  cat <file>           - Display file contents")
        print("  mkdir <directory>    - Create directory")
        print("  touch <file>         - Create empty file")
        print("  rm [-rf] <file>      - Remove file/directory (prompts without -f)")
        print("  mv <src> <dest>      - Move/rename file")
        print("  cp [-r] <src> <dest> - Copy file")
        print("  grep <pattern> <file> - Search for pattern in file")
        print()
        print("System Commands:")
        print("  whoami               - Display current user")
        print("  date                 - Display current date/time")
        print("  uname [options]      - Display system information")
        print("  nano <file>          - Edit file with nano")
        print("  fastfetch            - Display system info (auto-installs)")
        print()
        print("Python Commands:")
        print("  python [args]        - Run Python interpreter")
        print("  python3 [args]       - Run Python 3 interpreter")
        print("  pip [args]           - Run pip package manager")
        print("  pip3 [args]          - Run pip3 package manager")
        print()
        print("Features:")
        print("  ↑/↓ arrows           - Navigate command history")
        print("  Tab                  - Auto-complete commands/files")
        print("  -oszdtt flag         - Run any command in system shell")
        print("                         Example: htop -oszdtt")
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
        self.running = False
    
    def cmd_quit(self, args):
        """Quit and close the terminal window completely"""
        print("Closing terminal window...")
        # Exit the Python process with code 0
        # This will return control to the parent shell, which will then exit
        sys.exit(0)
    
    def cmd_about(self, args):
        """Display information about ZDTT Terminal"""
        print(f"\nZDTT Terminal v{self.version}")
        print("A custom terminal interface for Debian-based and Arch Linux systems")
        
        # Show distribution status
        if self.is_debian:
            print("Running on: Debian-based system (fully supported)")
        elif self.is_arch:
            print("Running on: Arch Linux (fully supported)")
        else:
            print("Running on: Unsupported system (limited support)")
        
        print()
        print("Features:")
        print("  • Automatic update checking on startup")
        print("  • Command history with ↑/↓ navigation (1000 commands)")
        print("  • Tab completion for commands and files")
        print("  • Command aliases (alias g=git)")
        print("  • Flexible time/date display with multiple formats")
        print("  • Colorized prompt")
        print("  • Smart banner (auto-hides on small terminals)")
        print("  • Plugin system with ZPS package manager")
        print("  • Plugin hot-reload (plugins reload)")
        print("  • Safe rm with confirmation prompts")
        print("  • Custom banner support (~/.zdtt/banner.txt)")
        print("  • Native command support")
        print("  • System command execution via -oszdtt flag")
        print("  • Clean, premium interface")
        print()
        print("Configuration:")
        print(f"  • ZDTT directory: {self.zdtt_dir}")
        print(f"  • Aliases: {self.aliases_file}")
        print(f"  • Custom banner: {self.banner_file}")
        print(f"  • Plugin errors: {self.log_file}")
        print()
    
    def cmd_history(self, args):
        """Display command history"""
        history_length = readline.get_current_history_length()
        
        if history_length == 0:
            print("No history available")
            return
        
        # Show last 50 commands by default
        limit = 50
        if args and args[0].isdigit():
            limit = int(args[0])
        
        start = max(1, history_length - limit + 1)
        
        print()
        for i in range(start, history_length + 1):
            cmd = readline.get_history_item(i)
            if cmd:
                print(f"{i:4d}  {cmd}")
        print()
    
    def cmd_plugins(self, args):
        """List or reload plugins"""
        # Check for reload subcommand
        if args and args[0] == 'reload':
            print("Reloading plugins...")
            # Remove plugin commands from command dict
            plugin_commands = []
            for cmd_name, cmd_func in list(self.commands.items()):
                # Check if it's not a built-in command (hacky but works)
                if hasattr(cmd_func, '__self__') and cmd_func.__self__ != self:
                    plugin_commands.append(cmd_name)
            
            for cmd in plugin_commands:
                del self.commands[cmd]
            
            # Clear aliases to avoid conflicts
            self.aliases.clear()
            self.load_aliases()
            
            # Reload plugins
            self.load_plugins()
            print("✓ Plugins reloaded successfully!")
            print()
            return
        
        # List plugins
        plugin_files = glob.glob(os.path.join(self.plugin_dir, "*.py"))
        
        if not plugin_files:
            print("\nNo plugins installed.")
            print(f"Plugin directory: {self.plugin_dir}")
            print("\nTo create a plugin, create a .py file with a register_commands() function")
            print("that returns a dictionary of command names to functions.")
            print("\nOr use: zps install <url> to install from a URL")
            print()
            return
        
        print(f"\nLoaded Plugins ({len(plugin_files)}):")
        for plugin_file in plugin_files:
            plugin_name = os.path.basename(plugin_file)[:-3]
            print(f"  • {plugin_name}")
        print()
        print(f"Plugin directory: {self.plugin_dir}")
        print(f"Error log: {self.log_file}")
        print()
        print("Commands:")
        print("  plugins reload  - Reload all plugins without restarting")
        print()
    
    def cmd_alias(self, args):
        """Create or display command aliases"""
        if not args:
            # Display all aliases
            if not self.aliases:
                print("\nNo aliases defined.")
                print("Usage: alias name=command")
                print("Example: alias g=git")
                print()
            else:
                print("\nDefined Aliases:")
                for name, command in sorted(self.aliases.items()):
                    print(f"  {name}={command}")
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
                print(f"Error: '{filename}' is not a Python file")
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
                
                print(f"✓ Plugin '{filename}' installed successfully!")
                print(f"  Location: {target_path}")
                print()
                print("To use the plugin:")
                print("  1. Type 'plugins reload' to load it now")
                print("  2. Or restart ZDTT")
                print()
                
            except urllib.error.HTTPError as e:
                print(f"Error: Failed to download plugin (HTTP {e.code})")
                print(f"URL: {url}")
            except urllib.error.URLError as e:
                print(f"Error: Failed to connect to server")
                print(f"Reason: {e.reason}")
            except Exception as e:
                print(f"Error: {e}")
            
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
                print(f"Error: Invalid format string - {e}")
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
        print(f"Status bar color updated to {color}.")
    
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
                if os.path.isfile(path):
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
    
    def cmd_fastfetch(self, args):
        """Display system info with fastfetch (auto-installs if needed)"""
        def _find_fastfetch_binary():
            """Return absolute path to fastfetch if available."""
            fastfetch_path = shutil.which('fastfetch')
            if fastfetch_path:
                return fastfetch_path
            
            # Fallback search in common locations
            common_paths = [
                '/usr/bin/fastfetch',
                '/usr/local/bin/fastfetch',
                os.path.expanduser('~/.local/bin/fastfetch'),
            ]
            for path in common_paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path
            return None
        
        def _build_install_command():
            """Return (cmd_list, manual_hint) based on distro/privileges."""
            manual_hint = None
            if self.is_debian:
                base_cmd = ['apt-get', 'install', '-y', 'fastfetch']
                manual_hint = "sudo apt-get install fastfetch"
            elif self.is_arch:
                base_cmd = ['pacman', '-S', '--noconfirm', 'fastfetch']
                manual_hint = "sudo pacman -S fastfetch"
            else:
                return None, None
            
            # Determine if sudo is needed
            geteuid = getattr(os, 'geteuid', None)
            is_root = geteuid is not None and geteuid() == 0
            sudo_path = shutil.which('sudo')
            
            if is_root:
                return base_cmd, manual_hint
            
            if sudo_path:
                return [sudo_path] + base_cmd, manual_hint
            
            # Cannot elevate automatically
            return None, manual_hint
        
        # Check if fastfetch is installed
        fastfetch_bin = _find_fastfetch_binary()
        
        if not fastfetch_bin:
            if not self.is_supported:
                print("fastfetch is not installed.")
                print("Auto-install is only supported on Debian-based and Arch Linux systems.")
                print("Please install fastfetch manually using your package manager:")
                print("  • Debian/Ubuntu: sudo apt-get install fastfetch")
                print("  • Arch/Manjaro: sudo pacman -S fastfetch")
                print("  • Fedora: sudo dnf install fastfetch")
                print("  • openSUSE: sudo zypper install fastfetch")
                return
            
            install_cmd, manual_hint = _build_install_command()
            if not install_cmd:
                print("fastfetch is not installed and cannot be auto-installed because elevated privileges")
                print("are required but 'sudo' was not found (or you're not running as root).")
                if manual_hint:
                    print(f"Try manually: {manual_hint}")
                else:
                    print("Please install fastfetch via your package manager.")
                return
            
            print("fastfetch is not installed. Installing...")
            print()
            try:
                subprocess.run(install_cmd, check=True)
                print()
                print("fastfetch installed successfully!")
                print()
            except subprocess.CalledProcessError:
                print("Failed to install fastfetch")
                if manual_hint:
                    print(f"Try manually: {manual_hint}")
                else:
                    print("Please install fastfetch via your package manager.")
                return
        
            fastfetch_bin = _find_fastfetch_binary()
            if not fastfetch_bin:
                print("fastfetch installation completed but binary was not found.")
                print("Ensure fastfetch is in your PATH and try again.")
                return
        
        subprocess.run([fastfetch_bin] + args)
    
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
    
    def execute_command(self, command_line):
        """Parse and execute a command"""
        if not command_line.strip():
            return
        
        # Expand aliases first
        command_line = self.expand_aliases(command_line)
        
        # Check for -oszdtt flag (Outside ZDTT)
        if '-oszdtt' in command_line:
            # Remove the -oszdtt flag and execute as system command
            system_command = command_line.replace('-oszdtt', '').strip()
            if system_command:
                try:
                    result = os.system(system_command)
                    # os.system returns the exit code
                    if result != 0:
                        pass  # Command already displayed its error
                except Exception as e:
                    print(f"Error executing command: {e}")
            else:
                print("No command specified with -oszdtt flag")
            return
        
        parts = command_line.strip().split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            print(f"Command not found: {cmd}")
            print("Type 'help' for available commands.")
            print("Tip: Use -oszdtt flag to run system commands")
    
    def run(self):
        """Main terminal loop"""
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
