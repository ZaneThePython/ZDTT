"""
System detection and persistent configuration helpers for ZDTT.
"""
import os
import sys
import shutil
import json

SUPPORTED_DEBIAN_IDS = {
    'debian', 'ubuntu', 'linuxmint', 'mint', 'pop', 'pop-os', 'pop_os',
    'elementary', 'zorin', 'kali', 'parrot', 'mx', 'mx-linux', 'deepin',
    'peppermint', 'raspbian', 'neon',
}

SUPPORTED_ARCH_IDS = {
    'arch', 'archlinux', 'manjaro', 'endeavouros', 'endeavour', 'arcolinux',
    'garuda', 'artix', 'blackarch', 'chakra',
}


def _parse_os_release():
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
    tokens = set()
    for value in values:
        if not value:
            continue
        normalized = value.replace('"', '').strip().lower()
        if not normalized:
            continue
        tokens.add(normalized)
        delimiters_replaced = normalized.replace('-', ' ').replace('_', ' ')
        for part in delimiters_replaced.split():
            if part:
                tokens.add(part)
    return tokens


def _detect_supported_distro():
    if os.path.exists('/etc/debian_version'):
        return 'debian'

    arch_markers = ('/etc/arch-release', '/etc/artix-release')
    if any(os.path.exists(path) for path in arch_markers):
        return 'arch'

    os_release = _parse_os_release()
    tokens = _collect_tokens(os_release.get('ID'), os_release.get('ID_LIKE'))

    if tokens & SUPPORTED_DEBIAN_IDS:
        return 'debian'
    if tokens & SUPPORTED_ARCH_IDS:
        return 'arch'

    if shutil.which('apt-get'):
        return 'debian'
    if shutil.which('pacman'):
        return 'arch'
    return 'other'


def _prompt_distro_override(detected_distro):
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


def _save_distro_preference(distro: str):
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
    """Detect supported distributions and warn when unsupported. Returns 'debian' | 'arch' | 'other'."""
    saved_distro = _load_saved_distro()
    if saved_distro:
        return saved_distro

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

    distro = _detect_supported_distro()
    if distro not in ('debian', 'arch'):
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

    distro = _prompt_distro_override(distro)
    _save_distro_preference(distro)
    return distro



