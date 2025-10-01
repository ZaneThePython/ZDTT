#!/usr/bin/env python3
"""
ZDTT Terminal - A custom terminal interface
Only works on Debian-based Linux systems
"""

import os
import sys
import getpass
import subprocess
import shutil
import readline
import glob
import atexit


def check_debian_based():
    """Check if the system is Debian-based Linux"""
    # Check if running on Linux
    if sys.platform != 'linux':
        print("Error: ZDTT Terminal only works on Debian-based Linux systems.")
        print(f"Detected platform: {sys.platform}")
        sys.exit(1)
    
    # Check for Debian-specific file
    if not os.path.exists('/etc/debian_version'):
        print("Error: ZDTT Terminal only works on Debian-based Linux systems.")
        print("This does not appear to be a Debian-based distribution.")
        print("(Debian, Ubuntu, Linux Mint, Pop!_OS, etc.)")
        sys.exit(1)
    
    # Optionally, display the Debian version
    try:
        with open('/etc/debian_version', 'r') as f:
            debian_version = f.read().strip()
            # Silently note the version (for debugging if needed)
    except:
        pass


class ZDTTTerminal:
    def __init__(self):
        self.username = getpass.getuser()
        self.running = True
        self.current_dir = os.getcwd()
        self.history_file = os.path.expanduser("~/.zdtt_history")
        self.plugin_dir = os.path.expanduser("~/.zdtt/plugins")
        
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
            # System commands
            'ls': self.cmd_ls,
            'pwd': self.cmd_pwd,
            'cd': self.cmd_cd,
            'cat': self.cmd_cat,
            'nano': self.cmd_nano,
            'neofetch': self.cmd_neofetch,
            'mkdir': self.cmd_mkdir,
            'touch': self.cmd_touch,
            'rm': self.cmd_rm,
            'mv': self.cmd_mv,
            'cp': self.cmd_cp,
            'whoami': self.cmd_whoami,
            'date': self.cmd_date,
            'uname': self.cmd_uname,
            'grep': self.cmd_grep,
        }
        
        # Setup readline history and tab completion
        self.setup_readline()
        
        # Load plugins
        self.load_plugins()
    
    def display_banner(self):
        """Display the ZDTT ASCII art banner"""
        banner = """
░█████████ ░███████   ░██████████░██████████
      ░██  ░██   ░██      ░██        ░██    
     ░██   ░██    ░██     ░██        ░██    
   ░███    ░██    ░██     ░██        ░██    
  ░██      ░██    ░██     ░██        ░██    
 ░██       ░██   ░██      ░██        ░██    
░█████████ ░███████       ░██        ░██    
                                            
                                            
ZDTT Terminal v0.0.1.alpha
"""
        print(banner)
    
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
            # Complete command names
            options = [cmd for cmd in self.commands.keys() if cmd.startswith(text)]
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
            except Exception as e:
                print(f"Warning: Failed to load plugin {plugin_name}: {e}")
    
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
        
        # Create colorized prompt
        # [username in green @ ZDTT path in blue]=>
        prompt = (f"[{self.COLOR_GREEN}{self.username}{self.COLOR_RESET}"
                 f"@{self.COLOR_CYAN}ZDTT{self.COLOR_RESET} "
                 f"{self.COLOR_BLUE}{display_path}{self.COLOR_RESET}]=> ")
        return prompt
    
    def cmd_help(self, args):
        """Display available commands"""
        print("\nZDTT Terminal Commands:")
        print("  help                 - Display this help message")
        print("  clear                - Clear the screen")
        print("  echo <message>       - Echo a message")
        print("  about                - About ZDTT Terminal")
        print("  history              - Show command history")
        print("  plugins              - List loaded plugins")
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
        print("  rm [-r] <file>       - Remove file or directory")
        print("  mv <src> <dest>      - Move/rename file")
        print("  cp [-r] <src> <dest> - Copy file")
        print("  grep <pattern> <file> - Search for pattern in file")
        print()
        print("System Commands:")
        print("  whoami               - Display current user")
        print("  date                 - Display current date/time")
        print("  uname [options]      - Display system information")
        print("  nano <file>          - Edit file with nano")
        print("  neofetch             - Display system info (auto-installs)")
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
        print("\nZDTT Terminal v0.0.1.alpha")
        print("A custom terminal interface for Debian-based Linux")
        print()
        print("Features:")
        print("  • Command history with ↑/↓ navigation")
        print("  • Tab completion for commands and files")
        print("  • Colorized prompt")
        print("  • Plugin system for extensibility")
        print("  • Native command support")
        print("  • System command execution via -oszdtt flag")
        print("  • Clean, premium interface")
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
        """List loaded plugins"""
        plugin_files = glob.glob(os.path.join(self.plugin_dir, "*.py"))
        
        if not plugin_files:
            print("\nNo plugins installed.")
            print(f"Plugin directory: {self.plugin_dir}")
            print("\nTo create a plugin, create a .py file with a register_commands() function")
            print("that returns a dictionary of command names to functions.")
            print()
            return
        
        print(f"\nLoaded Plugins ({len(plugin_files)}):")
        for plugin_file in plugin_files:
            plugin_name = os.path.basename(plugin_file)[:-3]
            print(f"  • {plugin_name}")
        print()
    
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
    
    def cmd_neofetch(self, args):
        """Display system info with neofetch (auto-installs if needed)"""
        # Check if neofetch is installed
        if not shutil.which('neofetch'):
            print("neofetch is not installed. Installing...")
            print()
            try:
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'neofetch'], check=True)
                print()
                print("neofetch installed successfully!")
                print()
            except subprocess.CalledProcessError:
                print("Failed to install neofetch")
                return
        
        subprocess.run(['neofetch'] + args)
    
    def execute_command(self, command_line):
        """Parse and execute a command"""
        if not command_line.strip():
            return
        
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
        self.display_banner()
        
        # Main command loop
        while self.running:
            try:
                command = input(self.get_prompt())
                self.execute_command(command)
            except KeyboardInterrupt:
                print("\nUse 'exit' to return to shell, or 'quit' to close the window.")
            except EOFError:
                print("\nGoodbye!")
                break


def main():
    # Check if running on Debian-based Linux
    check_debian_based()
    
    terminal = ZDTTTerminal()
    terminal.run()


if __name__ == "__main__":
    main()

