"""
Plugin utilities for ZDTT: AST validation, quarantine, and command validation.
"""

import os
import shutil
import ast
from typing import Dict, Callable, Iterable, Optional

# Protected command names that plugins cannot override
PROTECTED_COMMANDS = {
    'ssh', 'sudo', 'su', 'cp', 'mv', 'rm', 'ls', 'cat', 'chmod', 'chown',
    'history', 'zps', 'zdtt', 'pip', 'python', 'python3', 'curl', 'wget'
}


def validate_plugin_ast(plugin_code: str, plugin_name: str) -> bool:
    """
    Validate plugin AST to ensure no top-level code execution.
    Only allows: imports, function definitions, class definitions, and docstrings.
    Raises ValueError on violation.
    """
    try:
        tree = ast.parse(plugin_code)
    except SyntaxError as e:
        raise ValueError(f"Plugin has syntax errors: {e}")

    if not isinstance(tree, ast.Module):
        raise ValueError("Plugin must be a valid Python module")

    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(stmt, ast.ClassDef):
            continue
        if isinstance(stmt, ast.Expr):
            # Allow docstring literals
            if isinstance(stmt.value, (ast.Constant, ast.Str)):
                if isinstance(stmt.value, ast.Constant):
                    if isinstance(stmt.value.value, str):
                        continue
                else:
                    # ast.Str case (older Python)
                    continue
        raise ValueError(
            f"Plugin contains forbidden top-level statement: {stmt.__class__.__name__}. "
            "Plugins can only contain imports, functions, classes, and docstrings. "
            "No top-level code execution is allowed."
        )

    return True


def move_to_quarantine(plugin_file: str, quarantine_dir: str, logger) -> Optional[str]:
    """
    Move a plugin file to quarantine directory and log the reason via caller.
    Returns the final quarantine path or None on failure.
    """
    plugin_name = os.path.basename(plugin_file)
    os.makedirs(quarantine_dir, exist_ok=True)

    quarantine_path = os.path.join(quarantine_dir, plugin_name)
    counter = 1
    while os.path.exists(quarantine_path):
        name, ext = os.path.splitext(plugin_name)
        quarantine_path = os.path.join(quarantine_dir, f"{name}_{counter}{ext}")
        counter += 1

    try:
        shutil.move(plugin_file, quarantine_path)
        logger.warning(f"Plugin '{plugin_name}' quarantined")
        logger.warning(f"Moved to: {quarantine_path}")
        return quarantine_path
    except Exception as e:
        logger.error(f"Failed to quarantine plugin '{plugin_name}': {e}")
        return None


def validate_plugin_commands(
    plugin_commands: Dict[str, Callable],
    plugin_name: str,
    protected_commands: Iterable[str] = PROTECTED_COMMANDS,
) -> bool:
    """
    Ensure plugins do not override protected commands and values are callable.
    Raises ValueError on violation.
    """
    violations = [cmd for cmd in plugin_commands.keys() if cmd in protected_commands]
    if violations:
        raise ValueError(
            f"Plugin attempted to override protected commands: {', '.join(violations)}. "
            "This is a security violation and the plugin has been quarantined."
        )

    for cmd_name, cmd_func in plugin_commands.items():
        if not callable(cmd_func):
            raise ValueError(
                f"Plugin command '{cmd_name}' is not callable. All commands must be functions."
            )

    return True



