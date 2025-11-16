"""
System shell command execution utilities for ZDTT.
"""
import sys
import subprocess
import time as time_module


def execute_system_command(terminal, command: str):
    """Execute a system command with real-time I/O streaming."""
    status_bar_was_running = terminal.status_bar_thread and terminal.status_bar_thread.is_alive()
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=sys.stdin,
            bufsize=1,
            text=True,
            cwd=terminal.current_dir
        )

        early_output = []
        start_time = time_module.time()
        check_timeout = 0.1
        hide_output = False
        output_buffer = []

        try:
            while True:
                char = process.stdout.read(1)
                if not char:
                    if process.poll() is not None:
                        break
                    time_module.sleep(0.01)
                    continue

                if time_module.time() - start_time < check_timeout:
                    early_output.append(char)
                    combined = ''.join(early_output).lower()
                    if 'command not found' in combined or 'not found:' in combined:
                        hide_output = True
                        while process.poll() is None:
                            process.stdout.read(1)
                        break

                output_buffer.append(char)
                if char == '\n' or len(output_buffer) >= 1024:
                    if not hide_output:
                        sys.stdout.write(''.join(output_buffer))
                        sys.stdout.flush()
                    output_buffer.clear()

            if output_buffer and not hide_output:
                sys.stdout.write(''.join(output_buffer))
                sys.stdout.flush()

            process.wait()
        except BrokenPipeError:
            pass
    except KeyboardInterrupt:
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
        if not locals().get('hide_output', False):
            print(f"{terminal.COLOR_ERROR}Error executing command: {e}{terminal.COLOR_RESET}")
    finally:
        if status_bar_was_running:
            terminal._render_status_bar()



