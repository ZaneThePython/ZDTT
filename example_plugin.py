"""
Example ZDTT Plugin
This demonstrates how to create a plugin for ZDTT Terminal.

To install this plugin:
1. Copy this file to ~/.zdtt/plugins/
2. Restart ZDTT Terminal

The plugin will be loaded automatically.
"""

import subprocess
import os


def cmd_hello(args):
    """Say hello to the user"""
    if args:
        name = ' '.join(args)
        print(f"Hello, {name}! Welcome to ZDTT Terminal!")
    else:
        print("Hello! Welcome to ZDTT Terminal!")


def cmd_weather(args):
    """Display weather information using wttr.in"""
    location = args[0] if args else ""
    try:
        subprocess.run(['curl', f'wttr.in/{location}'])
    except Exception as e:
        print(f"Error fetching weather: {e}")
        print("Make sure curl is installed: sudo apt-get install curl")


def cmd_sysinfo(args):
    """Display detailed system information"""
    print("\n=== System Information ===\n")
    
    # Hostname
    print(f"Hostname: {os.uname().nodename}")
    
    # OS Info
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('PRETTY_NAME'):
                    os_name = line.split('=')[1].strip().strip('"')
                    print(f"OS: {os_name}")
                    break
    except:
        pass
    
    # Kernel
    print(f"Kernel: {os.uname().release}")
    
    # Architecture
    print(f"Architecture: {os.uname().machine}")
    
    # CPU Info
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'model name' in line:
                    cpu = line.split(':')[1].strip()
                    print(f"CPU: {cpu}")
                    break
    except:
        pass
    
    # Memory Info
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal' in line:
                    mem = int(line.split()[1]) // 1024
                    print(f"Memory: {mem} MB")
                    break
    except:
        pass
    
    print()


def register_commands():
    """
    This function is required for ZDTT to load the plugin.
    Return a dictionary of command names to functions.
    """
    return {
        'hello': cmd_hello,
        'weather': cmd_weather,
        'sysinfo': cmd_sysinfo,
    }

