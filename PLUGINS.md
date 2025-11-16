# 📘 **ZDTT Plugin Development Guide**

*Create safe, powerful extensions for the ZDTT Terminal.*

---

## 🟦 Introduction

ZDTT supports a secure, sandboxed plugin system that allows developers to extend the terminal with custom commands.

Plugins live inside:

```
~/.zdtt/plugins/
```

A plugin is simply a Python file that:

1. Contains **no top-level executable code**
2. Defines functions or classes
3. Defines a mandatory function:

   ```python
   def register_commands():
       return { "command": callable }
   ```

Plugins are automatically loaded when ZDTT starts or when you run:

```
plugins reload
```

---

# 🛡️ Plugin Security Model

ZDTT has strict safety validation to protect users from malicious plugins.
Every plugin must pass **six security layers**:

---

## **1. AST Validation**

At load time, ZDTT parses the plugin using Python’s AST.

Allowed at the top level:

* Imports
* From-imports
* Function definitions
* Class definitions
* A file-level docstring

Forbidden (**causes quarantine**):

* Print statements
* Assignments
* Function calls
* Loops
* Try/except blocks
* Any executable code
* Anything that runs automatically

Example of an unsafe plugin:

```python
print("hacked!")     # ❌ this will be quarantined
os.system("rm -rf /")  # ❌ also quarantined
```

Unsafe plugins are moved to:

```
~/.zdtt/quarantine/
```

---

## **2. Import Trust Prompt**

Plugins may import modules:

```python
import os
import subprocess
```

However:
**Any plugin with imports triggers a trust confirmation.**

If the user does **not** trust the plugin, it is quarantined.

If the user approves, the plugin name is added to:

```
config.json → trusted_plugins
```

Only trusted plugins may use `__import__`.

---

## **3. Sandboxed Execution**

Plugins run inside a restricted environment:

* Only safe builtins are exposed
* Dangerous builtins (like `exec` or `eval`) are blocked
* Imports only work for trusted plugins
* Code cannot escape the sandbox

---

## **4. register_commands() Validation**

Every plugin must define:

```python
def register_commands():
    return {"name": function}
```

ZDTT verifies:

* The function exists
* The return value is a dict
* All values are callable
* Command names are valid strings

---

## **5. Protected Command Names**

Plugins **cannot override** important commands such as:

```
ssh, sudo, su, cp, mv, rm, ls, cat,
chmod, chown, history, zps, zdtt,
pip, python, python3, curl, wget
```

Attempting to override them causes quarantine.

---

## **6. Runtime Registration**

Once the plugin passes all previous checks, ZDTT adds its commands to the shell environment.

Example:

```python
{
  "weather": cmd_weather,
  "hello": cmd_hello
}
```

These appear in autocomplete and `help`.

---

# 🟩 Plugin Structure

A minimal valid plugin:

```python
"""
My Plugin
"""

def cmd_test(args):
    print("Hello from ZDTT plugin!")

def register_commands():
    return {"test": cmd_test}
```

---

# 🟧 Arguments

ZDTT passes command arguments as a list.

Example:

```
hello world how are you
```

Results in:

```python
cmd_hello(["world", "how", "are", "you"])
```

---

# 🟪 Example Plugin (Official)

From `example_plugin.py`:

```python
"""
Example ZDTT Plugin
"""

import subprocess
import os

def cmd_hello(args):
    ...

def cmd_weather(args):
    ...

def cmd_sysinfo(args):
    ...

def register_commands():
    return {
        "hello": cmd_hello,
        "weather": cmd_weather,
        "sysinfo": cmd_sysinfo
    }
```

All three commands use argument lists exactly as ZDTT passes them.

---

# 🟫 Installing Plugins

### **Manual Install**

Place plugin file in:

```
~/.zdtt/plugins/
```

Then reload:

```
plugins reload
```

---

### **Install via ZPS**

Install directly from a URL:

```
zps install https://raw.githubusercontent.com/user/repo/plugin.py
```

ZPS will:

* Download the file
* Save it to your plugin directory
* Warn if it already exists
* Ask if you trust imports (if any)

---

# 🟨 Debugging Plugins

ZDTT logs plugin errors to:

```
~/.zdtt/plugin_errors.log
```

Quarantined plugins appear in:

```
~/.zdtt/quarantine/
```

Reload plugins:

```
plugins reload
```

---

# 🟩 Best Practices for Plugin Developers

✔ Wrap all code inside functions
✔ Avoid imports unless required
✔ Validate arg lists
✔ Use try/except around risky operations
✔ Keep commands short and simple
✔ Document your commands
✔ Never modify global state
✔ Don’t override protected commands

---

# 🟦 Advanced Plugin Tips

### Show usage/help

```python
def cmd_calc(args):
    """Usage: calc <expression>"""
    ...
```

ZDTT automatically pulls these docstrings into the `help` system.

### Combine args into a string

```python
expr = " ".join(args)
```

### Use subprocess safely

```python
try:
    subprocess.run(["ls"])
except Exception as e:
    print("Error:", e)
```

### Read files safely

Use try/except to avoid crashing the shell.

---

# 🟣 Full Plugin Template

```python
"""
Plugin Name: <your plugin>
Description: <what it does>
Author: <you>
"""

# Optional imports (will require trust prompt)
import subprocess

def cmd_example(args):
    print("Example plugin working!")

def register_commands():
    return {
        "example": cmd_example
    }
```