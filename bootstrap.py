#!/usr/bin/env python3
"""IVX Discord Lab bootstrapper: animated setup splash using only Python's standard library."""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "requirements.txt"
APP_FILE = ROOT / "app.py"
MINIMUM_PYTHON = (3, 10)


class BootstrapError(RuntimeError):
    """Actionable setup error shown in the splash screen."""


def _tail(text: str, limit: int = 1800) -> str:
    return text.strip()[-limit:] or "(No additional diagnostic output.)"


def _run_checked(args: list[str], *, label: str, emit: Callable[..., None]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BootstrapError(f"{label} could not finish.\n\n{exc}") from exc
    if result.returncode != 0:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
        raise BootstrapError(f"{label} failed (exit code {result.returncode}).\n\n{_tail(details)}")
    return result


def prepare_and_launch(emit: Callable[..., None]) -> subprocess.Popen[bytes]:
    """Create/repair .venv, install the UI dependency if needed, and launch only app.py."""
    if sys.version_info < MINIMUM_PYTHON:
        raise BootstrapError(
            f"Python 3.10 or newer is required. The selected interpreter is "
            f"{sys.version_info.major}.{sys.version_info.minor}."
        )
    for required in (APP_FILE, REQUIREMENTS):
        if not required.is_file():
            raise BootstrapError(f"Required file is missing:\n{required.name}\n\nExtract the complete project folder and retry.")

    emit("stage", 8, "Checking your Python environment", "Verifying Python 3.10 or newer.")
    if VENV.is_symlink():
        raise BootstrapError(
            "The .venv path is a symbolic link. For safety, this launcher will not delete or modify its target.\n\n"
            "Rename or remove that link yourself, then launch again."
        )

    env_valid = False
    if VENV_PYTHON.is_file():
        check = subprocess.run(
            [str(VENV_PYTHON), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if check.returncode == 0:
            env_valid = True
        else:
            emit("stage", 18, "Repairing the local environment", "The existing project environment is incomplete or out of date.")
            try:
                if VENV.is_dir():
                    shutil.rmtree(VENV)
                elif VENV.exists():
                    VENV.unlink()
            except OSError as exc:
                raise BootstrapError(f"The local .venv environment could not be repaired.\n\n{exc}") from exc
    elif VENV.exists():
        emit("stage", 18, "Repairing the local environment", "Removing an incomplete project environment.")
        try:
            if VENV.is_dir():
                shutil.rmtree(VENV)
            else:
                VENV.unlink()
        except OSError as exc:
            raise BootstrapError(f"The local .venv environment could not be repaired.\n\n{exc}") from exc

    if not env_valid:
        emit("stage", 25, "Creating your private workspace", "Creating the project-local .venv environment.")
        _run_checked(
            [sys.executable, "-m", "venv", str(VENV)],
            label="Creating the Python environment",
            emit=emit,
        )
        if not VENV_PYTHON.is_file():
            raise BootstrapError("Python reported success but .venv\\Scripts\\python.exe was not created.")

    emit("stage", 50, "Checking desktop components", "Checking the PySide6 / Qt interface dependency.")
    check = subprocess.run(
        [str(VENV_PYTHON), "-c", "import PySide6.QtWidgets"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if check.returncode != 0:
        emit("stage", 60, "Installing desktop components", "Downloading and installing PySide6. Keep this window open.")
        try:
            installer = subprocess.Popen(
                [
                    str(VENV_PYTHON), "-m", "pip", "install",
                    "--disable-pip-version-check", "-r", str(REQUIREMENTS),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            raise BootstrapError(f"The dependency installer could not start.\n\n{exc}") from exc

        recent_lines: list[str] = []
        if installer.stdout is not None:
            for line in installer.stdout:
                line = line.rstrip()
                if not line:
                    continue
                recent_lines.append(line)
                recent_lines = recent_lines[-5:]
                emit("detail", min(82, 60 + len(recent_lines) * 3), line[-120:])
        return_code = installer.wait()
        if return_code != 0:
            raise BootstrapError(
                "PySide6 installation failed. Check your internet connection and Python installation, then retry.\n\n"
                + _tail("\n".join(recent_lines))
            )

        verify = subprocess.run(
            [str(VENV_PYTHON), "-c", "import PySide6.QtWidgets"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        if verify.returncode != 0:
            raise BootstrapError(
                "PySide6 installation finished, but the Qt interface still cannot be imported.\n\n"
                + _tail(verify.stderr or verify.stdout)
            )

    emit("stage", 86, "Preparing IVX Discord Lab", "The environment is ready. Starting the desktop interface.")
    local_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "IVXDiscordLab"
    try:
        local_data.mkdir(parents=True, exist_ok=True)
        log_path = local_data / "app.log"
        with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
            process = subprocess.Popen(
                [str(VENV_PYTHON), str(APP_FILE)],
                cwd=ROOT,
                env={**os.environ, "PYTHONUTF8": "1"},
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
    except OSError as exc:
        raise BootstrapError(f"IVX Discord Lab could not be started.\n\n{exc}") from exc

    # Catch import/runtime failures that make the window close immediately.
    emit("stage", 94, "Opening your workspace", "Waiting for the desktop window to initialize.")
    time.sleep(1.0)
    exit_code = process.poll()
    if exit_code is not None:
        try:
            details = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            details = ""
        raise BootstrapError(
            f"The desktop app closed during startup (exit code {exit_code}).\n\n"
            f"Diagnostic log: {log_path}\n\n{_tail(details)}"
        )

    emit("stage", 100, "Ready", "IVX Discord Lab is running.")
    return process


def run_console() -> int:
    """Fallback for Python installations that do not include Tkinter."""
    def emit(event: str, percent: int = 0, detail: str = "") -> None:
        if event == "stage":
            print(f"[{percent:3d}%] {detail}", flush=True)
        elif event == "detail":
            print(f"       {detail}", flush=True)

    try:
        process = prepare_and_launch(emit)
    except BootstrapError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr, flush=True)
        return 1
    print("\nIVX Discord Lab has opened. This launcher will remain active until you close the app.", flush=True)
    return process.wait()


def run_gui() -> int:
    try:
        import tkinter as tk
    except ImportError:
        return run_console()

    events: queue.Queue[tuple] = queue.Queue()
    outcome: dict[str, object] = {"process": None, "error": None}
    width, height = 620, 390
    root = tk.Tk()
    root.title("IVX Discord Lab — Setup")
    root.configure(bg="#090b12")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{width}x{height}+{(screen_w-width)//2}+{(screen_h-height)//2}")
    root.protocol("WM_DELETE_WINDOW", lambda: None)

    canvas = tk.Canvas(root, width=width, height=height, highlightthickness=0, bd=0, bg="#090b12")
    canvas.pack(fill="both", expand=True)
    canvas.create_rectangle(12, 12, width - 12, height - 12, fill="#0d1019", outline="#252a3b", width=1)
    canvas.create_rectangle(30, 32, width - 30, 160, fill="#111522", outline="#252940", width=1)

    # The light-sweep beams are deliberately behind the title and brand mark.
    beams = []
    beam_colors = ["#17172c", "#202044", "#302b5b", "#4c417e", "#302b5b", "#202044"]
    for idx, color in enumerate(beam_colors):
        beams.append(canvas.create_polygon(-200, 40, -120, 40, -172, 155, -252, 155,
                                           fill=color, outline=""))
    canvas.create_rectangle(50, 52, 96, 98, fill="#7455ed", outline="#8c74ff", width=1)
    canvas.create_text(73, 75, text="IV", fill="#ffffff", font=("Segoe UI", 15, "bold"))
    canvas.create_text(112, 61, anchor="nw", text="IVX DISCORD LAB", fill="#f4f5ff",
                       font=("Segoe UI", 15, "bold"))
    canvas.create_text(112, 85, anchor="nw", text="DESKTOP WORKSPACE", fill="#9ca5bc",
                       font=("Segoe UI", 8, "bold"))
    canvas.create_text(51, 117, anchor="nw", text="Building a clean, isolated environment for your app.",
                       fill="#c5cadd", font=("Segoe UI", 10))
    canvas.create_text(51, 139, anchor="nw", text="This can take a little longer on the first launch.",
                       fill="#8089a1", font=("Segoe UI", 9))

    canvas.create_text(52, 184, anchor="nw", text="INITIALIZING WORKSPACE", fill="#9d8cff",
                       font=("Segoe UI", 8, "bold"))
    title_id = canvas.create_text(52, 203, anchor="nw", text="Checking your Python environment",
                                  fill="#edf0fa", font=("Segoe UI", 11, "bold"))
    detail_id = canvas.create_text(52, 228, anchor="nw", text="Preparing setup…", width=510,
                                   fill="#8993aa", font=("Segoe UI", 9), justify="left")
    track_id = canvas.create_rectangle(52, 270, width - 52, 279, fill="#252a3a", outline="")
    fill_id = canvas.create_rectangle(52, 270, 52, 279, fill="#8b72ff", outline="")
    percent_id = canvas.create_text(width - 52, 293, anchor="ne", text="0%",
                                    fill="#9aa4bb", font=("Segoe UI", 8, "bold"))
    footer_id = canvas.create_text(52, 326, anchor="nw", text="Preparing…",
                                   fill="#59647d", font=("Segoe UI", 8))
    close_button = tk.Button(
        root, text="Close", command=root.destroy, state="normal",
        bg="#202538", fg="#e3e7f4", activebackground="#303956",
        activeforeground="#ffffff", relief="flat", bd=0, padx=16, pady=5,
        font=("Segoe UI", 9, "bold"),
    )
    close_window_id = canvas.create_window(width - 62, 350, window=close_button, anchor="center", state="hidden")
    error_text = tk.Text(
        root, wrap="word", height=4, width=66, state="disabled",
        bg="#0a0d14", fg="#cbd2e3", insertbackground="#ffffff",
        relief="flat", bd=0, padx=8, pady=6,
        font=("Consolas", 8),
    )
    error_window_id = canvas.create_window(52, 282, window=error_text, anchor="nw",
                                           width=width - 104, height=65, state="hidden")
    failed = {"value": False}
    sweep_position = -260
    percent_value = {"value": 0}
    last_detail = {"value": "Preparing setup…"}

    def set_stage(percent: int, title: str, detail: str) -> None:
        percent = max(0, min(100, percent))
        percent_value["value"] = max(percent_value["value"], percent)
        canvas.itemconfigure(title_id, text=title)
        canvas.itemconfigure(detail_id, text=detail)
        canvas.coords(fill_id, 52, 270, 52 + (width - 104) * percent_value["value"] / 100, 279)
        canvas.itemconfigure(percent_id, text=f"{percent_value['value']}%")
        canvas.itemconfigure(footer_id, text="INSTALLATION OUTPUT  ·  LOCAL ONLY" if percent < 100 else "STARTUP COMPLETE")
        last_detail["value"] = detail

    def animate() -> None:
        nonlocal sweep_position
        sweep_position += 7
        if sweep_position > width + 260:
            sweep_position = -260
        for index, item in enumerate(beams):
            x = sweep_position + index * 82
            canvas.coords(item, x, 40, x + 88, 40, x + 35, 155, x - 53, 155)
        # Gentle moving highlight in the progress track, so long installs still look alive.
        if not failed["value"] and percent_value["value"] < 99:
            x = 52 + ((time.monotonic() * 80) % (width - 104))
            canvas.create_line(x, 270, min(width - 52, x + 28), 270, fill="#c0b5ff", width=2, tags="progress-glint")
            glints = canvas.find_withtag("progress-glint")
            if len(glints) > 1:
                canvas.delete(glints[0])
        root.after(35, animate)

    def poll_events() -> None:
        try:
            while True:
                event = events.get_nowait()
                kind = event[0]
                if kind == "stage":
                    _, percent, title, detail = event
                    set_stage(percent, title, detail)
                elif kind == "detail":
                    _, percent, detail = event
                    percent_value["value"] = max(percent_value["value"], percent)
                    canvas.itemconfigure(detail_id, text=detail)
                    canvas.coords(fill_id, 52, 270, 52 + (width - 104) * percent_value["value"] / 100, 279)
                    canvas.itemconfigure(percent_id, text=f"{percent_value['value']}%")
                    last_detail["value"] = detail
                elif kind == "success":
                    outcome["process"] = event[1]
                    set_stage(100, "Workspace ready", "The desktop window is open. Enjoy IVX Discord Lab.")
                    root.after(450, root.destroy)
                    return
                elif kind == "error":
                    outcome["error"] = event[1]
                    failed["value"] = True
                    error_message = str(event[1])
                    summary = error_message.split("\n\n", 1)[0][:220]
                    set_stage(percent_value["value"], "Setup could not finish", summary)
                    canvas.itemconfigure(detail_id, text="Full diagnostic details are shown below.")
                    canvas.itemconfigure(track_id, state="hidden")
                    canvas.itemconfigure(fill_id, state="hidden")
                    canvas.itemconfigure(percent_id, state="hidden")
                    canvas.itemconfigure(footer_id, text="STARTUP FAILED  ·  REVIEW DETAILS")
                    canvas.delete("progress-glint")
                    error_text.configure(state="normal")
                    error_text.delete("1.0", "end")
                    error_text.insert("1.0", error_message[-1800:])
                    error_text.configure(state="disabled")
                    canvas.itemconfigure(error_window_id, state="normal")
                    canvas.itemconfigure(close_window_id, state="normal")
                    root.protocol("WM_DELETE_WINDOW", root.destroy)
        except queue.Empty:
            pass
        root.after(100, poll_events)

    def worker() -> None:
        try:
            def emit(*event: object) -> None:
                events.put(tuple(event))
            process = prepare_and_launch(emit)
            events.put(("success", process))
        except Exception as exc:
            events.put(("error", str(exc)))

    threading.Thread(target=worker, name="ivx-bootstrap", daemon=True).start()
    root.after(35, animate)
    root.after(100, poll_events)
    root.mainloop()

    if outcome["error"] is not None:
        return 1
    process = outcome["process"]
    if isinstance(process, subprocess.Popen):
        return process.wait()
    return 1


def main() -> int:
    if sys.version_info < MINIMUM_PYTHON:
        print("Python 3.10 or newer is required to start IVX Discord Lab.", file=sys.stderr)
        return 1
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
