"""
UI helpers for ZDTT: banner, compatibility warning, and prompt.
"""
import os
import shutil


def display_banner(terminal):
    print()
    try:
        term_size = shutil.get_terminal_size()
        min_height = 13 if not terminal.is_supported else 11
        min_width = 44
        if term_size.columns < min_width or term_size.lines < min_height:
            print(f"ZDTT Terminal v{terminal.version}")
            if not terminal.is_supported:
                _show_compatibility_warning(terminal)
            print()
            return
    except Exception:
        pass

    if os.path.exists(terminal.banner_file):
        try:
            with open(terminal.banner_file, 'r') as f:
                custom_banner = f.read()
                if '{version}' in custom_banner:
                    custom_banner = custom_banner.replace('{version}', terminal.version)
                print(custom_banner)
                if not terminal.is_supported:
                    _show_compatibility_warning(terminal)
                return
        except Exception as e:
            import logging
            logging.error(f"Failed to load custom banner: {e}")

    banner = f"""
░█████████ ░███████   ░██████████░██████████
      ░██  ░██   ░██      ░██        ░██    
     ░██   ░██    ░██     ░██        ░██    
   ░███    ░██    ░██     ░██        ░██    
  ░██      ░██    ░██     ░██        ░██    
 ░██       ░██   ░██      ░██        ░██    
░█████████ ░███████       ░██        ░██    
                                            
                                            
ZDTT Terminal v{terminal.version}
"""
    print(banner)
    if not terminal.is_supported:
        _show_compatibility_warning(terminal)


def _show_compatibility_warning(terminal):
    if terminal.is_supported:
        return
    print()
    print("⚠️  Running on unsupported system - limited support")
    print("    Tested on Debian-based and Arch Linux distributions.")
    print()


def get_prompt(terminal):
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        display_path = "~" + cwd[len(home):]
    else:
        display_path = cwd

    RL_PROMPT_START = '\001'
    RL_PROMPT_END = '\002'
    prompt = (f"{RL_PROMPT_START}{terminal.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}┌─{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END}"
              f"[{RL_PROMPT_START}{terminal.COLOR_BRIGHT_GREEN}{RL_PROMPT_END}{terminal.username}"
              f"{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END}"
              f"{RL_PROMPT_START}{terminal.COLOR_BRIGHT_WHITE}{RL_PROMPT_END}@{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END}"
              f"{RL_PROMPT_START}{terminal.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}ZDTT{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END} "
              f"{RL_PROMPT_START}{terminal.COLOR_BRIGHT_BLUE}{RL_PROMPT_END}{display_path}"
              f"{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END}]"
              f"{RL_PROMPT_START}{terminal.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}─{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END}\n"
              f"{RL_PROMPT_START}{terminal.COLOR_BRIGHT_CYAN}{RL_PROMPT_END}└─{RL_PROMPT_START}{terminal.COLOR_BRIGHT_MAGENTA}{RL_PROMPT_END}➜{RL_PROMPT_START}{terminal.COLOR_RESET}{RL_PROMPT_END} ")
    return prompt



