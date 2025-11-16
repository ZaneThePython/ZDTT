# ZDTT Terminal

A Python-based, Linux-first custom shell environment with plugin support, aliases, banners, and a modern command experience.
ZDTT wraps your system shell, adds its own built-in commands, and enhances your workflow instead of replacing your OS shell.

---

## ✨ Features

### ✔ Command History

Up/Down arrows navigate session history using Python’s `readline` module.

### ✔ Tab Completion

Auto-complete commands and filesystem paths.

### ✔ Colorized Prompt

ZDTT provides a custom prompt with color styling.
On Linux: supports full status bar.
On macOS: status bar disabled automatically due to OS cursor fight.

### ✔ Plugin System

Python-based plugin loader with AST security checks.
Plugins can register new ZDTT commands without modifying core files.

### ✔ Custom Aliases

Aliases are loaded from `~/.zdtt/aliases` and behave identically to shell shortcuts.

### ✔ Custom Banner Support

If `~/.zdtt/banner.txt` exists, it is displayed on launch.

### ✔ Distro Detection

ZDTT detects which major family you’re on:
- Debian-based
- Arch-based
- macOS

Used to determine:
- the correct sysfetch tool
- correct default package manager names
- correct onboarding messages

### ✔ Native Shell Command Relay

If a command is not a built-in ZDTT command or plugin command, it is passed directly to your real shell (bash, zsh, etc.).

### ✔ Status Bar (Linux only)

A background thread draws a live status bar showing time and system state.
Disabled automatically on macOS.

### ✔ Built-in Commands

* `help`
* `clear`
* `about`
* `history`
* `exit`
* `quit`
* `sysfetch`
* `time`
* `statusbar color <name>`
* plus plugin commands

---

## 🚀 Installation

### Quick Install

```bash
curl -O https://zdtt-sources.zane.org/install.sh && chmod +x install.sh && ./install.sh
```

The installer:

* Detects Debian, Arch, or macOS
* Installs Python 3 if needed
* Installs ZDTT to ~/.local/bin
* Sets up the `zdtt` command

### Manual Install

```bash
git clone https://github.com/ZaneThePython/ZDTT
cd ZDTT
chmod +x install.sh
./install.sh
```

---

## 📖 Usage

### Start ZDTT

```bash
zdtt start
```

### Management Commands

```bash
zdtt update
zdtt version
zdtt github
zdtt uninstall
```

---

## 🔌 Plugin System

ZDTT supports simple Python plugins stored in:

```
~/.zdtt/plugins/
```

Each plugin must define:

```python
def register_commands():
    return {"yourcmd": your_function}
```

Plugins are sandboxed using AST:

* No top-level execution allowed
* Only imports, functions, classes permitted
* Unsafe plugins are quarantined automatically

Reload plugins inside ZDTT:

```
plugins reload
```

Install via URL:

```
zps install <url>
```

See:

* `example_plugin.py`
* `PLUGINS.md`

---

## ⚙ Configuration

### Aliases

Store aliases in:

```
~/.zdtt/aliases
```

Or create them live:

```
alias ll=ls -la
unalias ll
```

### Banner

Add a custom banner in:

```
~/.zdtt/banner.txt
```

### Status Bar Color

```
statusbar color blue
```

Colors supported:
`blue red green cyan magenta yellow white black`

---

## 🖥 Supported Systems

### ✔ Full Support

* Debian-based distros
* Arch-based distros
* macOS (Status bar disabled automatically)

### ⚠ Limited Support

Other distros can run ZDTT but:

* auto-install may not work
* sysfetch may not detect tools
* package-manager messages may be incorrect

---

## 🛠 Development

ZDTT is written in Python and uses:

* `readline` for history & completion
* `threading` for status bar updates
* `ast` for plugin security
* `subprocess` for system command execution
* `os` and `shutil` for path and environment detection

### Project Structure

```
ZDTT/
├── terminal.py
├── install.sh
├── version.txt
├── example_plugin.py
├── example_aliases
├── example_banner.txt
├── PLUGINS.md
└── README.md
```

---

## 🤝 Contributing

PRs welcome!
ZDTT is early in development and evolving quickly.

---

## 🔗 Links

* GitHub: [https://github.com/ZaneThePython/ZDTT](https://github.com/ZaneThePython/ZDTT)
* Main site: [https://zdtt.zane.org](https://zdtt.zane.org)

---

## 💬 Notes

ZDTT is not a full standalone shell *yet* — it wraps your system shell and enhances it.
A full independent shell may come in the future.
Plugins may import Python modules, but may not execute code at import time.

---