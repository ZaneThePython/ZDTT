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
import ast
from datetime import datetime
import urllib.request
import urllib.error
import time as time_module

from zdtt.plugins import (
    PROTECTED_COMMANDS as PLUGIN_PROTECTED_COMMANDS,
    validate_plugin_ast as plugins_validate_ast,
    validate_plugin_commands as plugins_validate_commands,
    move_to_quarantine as plugins_move_to_quarantine,
)
from zdtt.config import (
    check_system_compatibility,
)
from zdtt import status_bar as sb
from zdtt.shell import execute_system_command as shell_execute
from zdtt.ui import display_banner as ui_display_banner, get_prompt as ui_get_prompt

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

# Protected command names that plugins cannot override (sourced from plugins module)
PROTECTED_COMMANDS = PLUGIN_PROTECTED_COMMANDS

# Helper for status bar module to get current color codes
def _STATUS_BAR_COLORS_LOOKUP(self):
    return STATUS_BAR_COLORS.get(self.status_bar_color, ('44', '97'))


## moved to zdtt.config


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
        self.quarantine_dir = os.path.join(self.zdtt_dir, "quarantine")
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
        self.safe_mode = False  # Safe mode flag (no plugins loaded)
        self.quarantine_warnings = []  # Store warnings for plugins quarantined at startup
        self.trusted_plugins = set()  # Plugins allowed to use imports
        # Expose STATUS_BAR_COLORS lookup to status bar module
        self.STATUS_BAR_COLORS_LOOKUP = lambda: _STATUS_BAR_COLORS_LOOKUP(self)
        
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
        
        # Load plugins (unless in safe mode)
        if not self.safe_mode:
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
            # Trusted plugins that are allowed to use imports
            trusted = data.get('trusted_plugins', [])
            if isinstance(trusted, list):
                self.trusted_plugins = set(trusted)
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
        # Persist trusted plugins as a sorted list for readability
        data['trusted_plugins'] = sorted(self.trusted_plugins)
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
        ui_display_banner(self)
    
    def _show_compatibility_warning(self):
        """Show compatibility warning for unsupported systems"""
        from zdtt.ui import _show_compatibility_warning as ui_warn
        ui_warn(self)
    
    def initialize_status_bar(self):
        """Reserve the first terminal row and start the status bar thread."""
        sb.initialize_status_bar(self)
    
    def shutdown_status_bar(self):
        """Stop the status bar thread and release terminal state."""
        sb.shutdown_status_bar(self)
    
    def _start_status_bar_thread(self):
        sb.start_status_bar_thread(self)
    
    def _status_bar_loop(self):
        sb.status_bar_loop(self)
    
    def _render_status_bar(self):
        """Render a single-line status bar with branding and time."""
        sb.render_status_bar(self)
    
    def _build_status_bar_text(self):
        """Render a single-line status bar with enhanced branding and time."""
        return sb.build_status_bar_text(self)
    
    def _set_scroll_region(self):
        """Reserve the top row for the status bar."""
        sb.set_scroll_region(self)
    
    def _reset_scroll_region(self):
        """Restore default scrolling behavior."""
        sb.reset_scroll_region(self)
    
    def _handle_resize(self, signum=None, frame=None):
        """Handle terminal resize event (SIGWINCH)."""
        sb.handle_resize(self, signum, frame)

    def _spawn_thread(self, target, name):
        return threading.Thread(target=target, name=name, daemon=True)
    
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
    
    def _validate_plugin_ast(self, plugin_code, plugin_name):
        # Delegate to plugins module
        return plugins_validate_ast(plugin_code, plugin_name)
    
    def _move_to_quarantine(self, plugin_file, reason):
        # Delegate to plugins module
        path = plugins_move_to_quarantine(plugin_file, self.quarantine_dir, logging)
        if path:
            logging.warning(f"Reason: {reason}")
        return path
    
    def _validate_plugin_commands(self, plugin_commands, plugin_name):
        # Delegate to plugins module
        return plugins_validate_commands(plugin_commands, plugin_name, PROTECTED_COMMANDS)
    
    def load_plugins(self):
        """Load plugin commands from the plugins directory with security validation."""
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir, exist_ok=True)
            return
        
        # Ensure quarantine directory exists
        os.makedirs(self.quarantine_dir, exist_ok=True)

        # Look for Python files in the plugins directory
        plugin_files = glob.glob(os.path.join(self.plugin_dir, "*.py"))
        loaded_count = 0
        failed_count = 0
        quarantined_count = 0

        for plugin_file in plugin_files:
            plugin_name = os.path.basename(plugin_file)[:-3]
            
            try:
                # Read plugin file
                with open(plugin_file, 'r') as f:
                    plugin_code = f.read()

                # Step 1: AST validation - check for top-level code
                try:
                    self._validate_plugin_ast(plugin_code, plugin_name)
                except ValueError as e:
                    # Quarantine the plugin
                    self._move_to_quarantine(plugin_file, f"AST validation failed: {e}")
                    quarantined_count += 1
                    warning_msg = (
                        f"{self.COLOR_ERROR}🚨 SECURITY WARNING: Plugin '{plugin_name}' has been quarantined!{self.COLOR_RESET}\n"
                        f"  Reason: {e}\n"
                        f"  The plugin attempted unsafe operations and has been disabled.\n"
                        f"  Check {self.quarantine_dir} for details.\n"
                    )
                    # Store warning to display after banner
                    self.quarantine_warnings.append(warning_msg)
                    continue

                # Step 2: Detect import usage and, if present, require trust
                plugin_uses_imports = False
                try:
                    tree = ast.parse(plugin_code)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            plugin_uses_imports = True
                            break
                except SyntaxError:
                    # Should already have been caught by _validate_plugin_ast, but be defensive
                    plugin_uses_imports = False

                plugin_trusted = False
                if plugin_uses_imports:
                    if plugin_name in self.trusted_plugins:
                        plugin_trusted = True
                    else:
                        print()
                        print(f"{self.COLOR_WARNING}⚠ Plugin '{plugin_name}' is requesting to use imports.{self.COLOR_RESET}")
                        print(f"{self.COLOR_DIM}  Imports can load external Python modules. Only trust plugins from sources you recognize.{self.COLOR_RESET}")
                        answer = input("Do you trust this plugin and allow imports? (yes/no): ").strip().lower()
                        if answer == "yes":
                            self.trusted_plugins.add(plugin_name)
                            # Persist updated trust list
                            try:
                                self.save_preferences()
                            except Exception as e:
                                logging.error(f"Failed to save trusted plugins list: {e}")
                            plugin_trusted = True
                            print(f"{self.COLOR_BRIGHT_GREEN}✓ Plugin '{plugin_name}' marked as trusted for imports.{self.COLOR_RESET}")
                        else:
                            # User did not trust the plugin; quarantine it
                            reason = "Plugin uses imports and was not trusted by the user."
                            self._move_to_quarantine(plugin_file, reason)
                            quarantined_count += 1
                            warning_msg = (
                                f"{self.COLOR_ERROR}🚨 SECURITY WARNING: Plugin '{plugin_name}' has been quarantined!{self.COLOR_RESET}\n"
                                f"  Reason: {reason}\n"
                                f"  The plugin attempted to use imports and has been disabled.\n"
                                f"  Check {self.quarantine_dir} for details.\n"
                            )
                            self.quarantine_warnings.append(warning_msg)
                            continue

                # Step 3: Sandboxed execution
                # Create a restricted namespace (sandbox)
                safe_builtins = {
                    # Only allow safe builtins
                    'len': len, 'str': str, 'int': int, 'float': float,
                    'bool': bool, 'list': list, 'dict': dict, 'tuple': tuple,
                    'set': set, 'frozenset': frozenset, 'range': range,
                    'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter,
                    'sorted': sorted, 'reversed': reversed, 'min': min, 'max': max,
                    'sum': sum, 'abs': abs, 'round': round, 'any': any, 'all': all,
                    'isinstance': isinstance, 'type': type, 'hasattr': hasattr,
                    'getattr': getattr, 'setattr': setattr, 'delattr': delattr,
                    'callable': callable, 'print': print, 'repr': repr,
                    # Exception classes (safe, required for normal Python code)
                    'BaseException': BaseException,
                    'Exception': Exception,
                    'ImportError': ImportError,
                    'NameError': NameError,
                    'ValueError': ValueError,
                    'TypeError': TypeError,
                    'RuntimeError': RuntimeError,
                }

                # Allow imports only for trusted plugins that use them
                if plugin_uses_imports and plugin_trusted:
                    safe_builtins['__import__'] = __import__

                sandbox = {
                    '__builtins__': safe_builtins
                }
                
                # Execute plugin in sandbox
                try:
                    exec(plugin_code, sandbox)
                except Exception as e:
                    failed_count += 1
                    logging.error(f"Failed to execute plugin '{plugin_name}': {str(e)}")
                    logging.error(f"Plugin file: {plugin_file}")
                    continue
                
                # Step 3: Check for register_commands function
                if 'register_commands' not in sandbox:
                    raise ValueError("Plugin missing register_commands() function")
                
                # Step 4: Call register_commands and validate return value
                try:
                    plugin_commands = sandbox['register_commands']()
                except Exception as e:
                    failed_count += 1
                    logging.error(f"register_commands() failed for plugin '{plugin_name}': {str(e)}")
                    continue
                
                if not isinstance(plugin_commands, dict):
                    raise ValueError("register_commands() must return a dictionary")
                
                # Step 5: Validate commands (protected names and callables)
                try:
                    self._validate_plugin_commands(plugin_commands, plugin_name)
                except ValueError as e:
                    # Quarantine the plugin
                    self._move_to_quarantine(plugin_file, f"Command validation failed: {e}")
                    quarantined_count += 1
                    warning_msg = (
                        f"{self.COLOR_ERROR}🚨 SECURITY WARNING: Plugin '{plugin_name}' has been quarantined!{self.COLOR_RESET}\n"
                        f"  Reason: {e}\n"
                        f"  The plugin attempted to override protected commands and has been disabled.\n"
                        f"  Check {self.quarantine_dir} for details.\n"
                    )
                    # Store warning to display after banner
                    self.quarantine_warnings.append(warning_msg)
                    continue
                
                # Step 6: All checks passed - register the commands
                self.commands.update(plugin_commands)
                self.plugin_command_names.update(plugin_commands.keys())
                loaded_count += 1
                    
            except Exception as e:
                failed_count += 1
                logging.error(f"Failed to load plugin '{plugin_name}': {str(e)}")
                logging.error(f"Plugin file: {plugin_file}")
        
        # Store summary warning if any plugins were quarantined
        if quarantined_count > 0:
            summary_warning = (
                f"{self.COLOR_ERROR}🚨 {quarantined_count} plugin(s) quarantined due to security violations!{self.COLOR_RESET}\n"
                f"  Check {self.quarantine_dir} for quarantined plugins.\n"
            )
            self.quarantine_warnings.append(summary_warning)
        
        # Note: Individual warnings and summary are stored in self.quarantine_warnings
        # They will be displayed after the banner in run() method
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
        return ui_get_prompt(self)
    
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
            
            # Clear previous warnings
            self.quarantine_warnings = []
            # Reload plugins
            self.load_plugins()
            # Display any new quarantine warnings
            if self.quarantine_warnings:
                print()
                for warning in self.quarantine_warnings:
                    print(warning)
                print()
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

        # Add --auto flag to enable auto-update (skip prompt)
        update_args = ['update', '--auto'] + args

        if zdtt_wrapper:
            subprocess.run([zdtt_wrapper] + update_args)
            return

        if os.path.isfile(installer_script):
            subprocess.run(['bash', installer_script] + update_args)
            return

        print("Unable to locate the ZDTT updater.")
        print("Re-run the installer script or use 'zdtt update' from your shell if available.")
    
    def _execute_system_command(self, command):
        """Execute a system command with real-time I/O streaming."""
        shell_execute(self, command)

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
        
        # Display security warnings for quarantined plugins (if any)
        if self.quarantine_warnings:
            print()
            for warning in self.quarantine_warnings:
                print(warning)
            print()
        
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
    # Parse command line arguments
    safe_mode = '--safe' in sys.argv
    
    # Check system compatibility
    distro = check_system_compatibility()
    
    terminal = ZDTTTerminal(distro=distro)
    terminal.safe_mode = safe_mode
    
    if safe_mode:
        print(f"{terminal.COLOR_WARNING}⚠ Safe mode enabled - plugins will not be loaded{terminal.COLOR_RESET}")
        print()
    
    terminal.run()


if __name__ == "__main__":
    main()
