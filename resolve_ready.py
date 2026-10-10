#!/usr/bin/env python3
"""
ResolveReady — dark-themed video converter for DaVinci Resolve on Linux.

Requirements (Arch Linux):
    sudo pacman -S ffmpeg tk python

Run:
    python resolve_ready.py
"""

import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

APP_NAME = "ResolveReady"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

# Dark palette
BG = "#101116"
PANEL = "#191b24"
PANEL_2 = "#222531"
BORDER = "#303342"
TEXT = "#f2f3f8"
MUTED = "#a0a5b7"
ACCENT = "#8b7cff"
ACCENT_HOVER = "#a094ff"
GREEN = "#61d6a4"
RED = "#ff777f"


class ResolveReadyApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("900x680")
        self.root.minsize(760, 570)
        self.root.configure(bg=BG)

        self.files = []
        self.events = queue.Queue()
        self.worker = None
        self.is_converting = False
        self.output_dir = tk.StringVar(value=str(Path.home() / "Videos" / "ResolveReady"))
        self.profile = tk.StringVar(value="DNxHR SQ")
        self.keep_audio = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Add videos to get started.")
        self.progress_text = tk.StringVar(value="Ready")
        self.current_file = tk.StringVar(value="No file selected")
        self._build_ui()
        self.root.after(100, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(24, 18))

        logo = tk.Canvas(header, width=46, height=46, bg=BG, highlightthickness=0)
        logo.pack(side="left")
        logo.create_rounded_rect = None
        logo.create_rectangle(3, 3, 43, 43, fill=ACCENT, outline="", width=0)
        logo.create_text(23, 23, text="R", fill="#ffffff", font=("TkDefaultFont", 22, "bold"))

        title_area = tk.Frame(header, bg=BG)
        title_area.pack(side="left", padx=13)
        tk.Label(title_area, text="ResolveReady", bg=BG, fg=TEXT,
                 font=("TkDefaultFont", 21, "bold")).pack(anchor="w")
        tk.Label(title_area, text="Make your footage DaVinci Resolve-friendly",
                 bg=BG, fg=MUTED, font=("TkDefaultFont", 10)).pack(anchor="w", pady=(2, 0))

        tk.Label(header, text="LINUX  •  FFMPEG", bg=PANEL_2, fg=MUTED,
                 font=("TkDefaultFont", 9, "bold"), padx=12, pady=7).pack(side="right", pady=6)

        # Main content
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=28)

        # Files card
        files_card = self._card(main)
        files_card.pack(fill="both", expand=True)

        row = tk.Frame(files_card, bg=PANEL)
        row.pack(fill="x", padx=18, pady=(16, 10))
        tk.Label(row, text="Your videos", bg=PANEL, fg=TEXT,
                 font=("TkDefaultFont", 13, "bold")).pack(side="left")
        self.file_count = tk.Label(row, text="0 files", bg=PANEL, fg=MUTED,
                                   font=("TkDefaultFont", 9))
        self.file_count.pack(side="left", padx=10)
        self._button(row, "＋ Add videos", self.add_files, primary=True).pack(side="right")
        self._button(row, "Add folder", self.add_folder).pack(side="right", padx=(0, 8))

        list_frame = tk.Frame(files_card, bg=PANEL_2, highlightbackground=BORDER,
                              highlightthickness=1)
        list_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self.listbox = tk.Listbox(
            list_frame, bg=PANEL_2, fg=TEXT, selectbackground="#383451",
            selectforeground="#ffffff", activestyle="none", borderwidth=0,
            highlightthickness=0, font=("TkFixedFont", 10),
            selectmode=tk.EXTENDED
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=5)

        bottom_files = tk.Frame(files_card, bg=PANEL)
        bottom_files.pack(fill="x", padx=18, pady=(0, 16))
        tk.Label(bottom_files, text="Original files are never modified.",
                 bg=PANEL, fg=MUTED, font=("TkDefaultFont", 9)).pack(side="left")
        self._button(bottom_files, "Remove selected", self.remove_selected).pack(side="right")
        self._button(bottom_files, "Clear", self.clear_files).pack(side="right", padx=(0, 7))

        # Settings card
        settings = self._card(main)
        settings.pack(fill="x", pady=(14, 0))
        tk.Label(settings, text="Conversion settings", bg=PANEL, fg=TEXT,
                 font=("TkDefaultFont", 13, "bold")).pack(anchor="w", padx=18, pady=(15, 12))

        settings_grid = tk.Frame(settings, bg=PANEL)
        settings_grid.pack(fill="x", padx=18, pady=(0, 16))
        settings_grid.columnconfigure(0, weight=1)
        settings_grid.columnconfigure(1, weight=1)

        profile_box = tk.Frame(settings_grid, bg=PANEL)
        profile_box.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        tk.Label(profile_box, text="VIDEO PROFILE", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 6))
        self.profile_combo = ttk.Combobox(
            profile_box, textvariable=self.profile, state="readonly",
            values=("DNxHR SQ", "DNxHR HQ", "DNxHR HQX")
        )
        self.profile_combo.pack(fill="x", ipady=5)

        output_box = tk.Frame(settings_grid, bg=PANEL)
        output_box.grid(row=0, column=1, sticky="ew")
        tk.Label(output_box, text="OUTPUT FOLDER", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 6))
        out_row = tk.Frame(output_box, bg=PANEL)
        out_row.pack(fill="x")
        self.output_entry = tk.Entry(
            out_row, textvariable=self.output_dir, bg=PANEL_2, fg=TEXT,
            insertbackground=TEXT, relief="flat", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=ACCENT
        )
        self.output_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 7))
        self._button(out_row, "Browse", self.choose_output).pack(side="right")

        tk.Checkbutton(
            settings, text="Keep audio (PCM 48 kHz)", variable=self.keep_audio,
            bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=TEXT,
            selectcolor=PANEL_2, font=("TkDefaultFont", 10), bd=0,
            highlightthickness=0
        ).pack(anchor="w", padx=18, pady=(0, 14))

        # Footer / progress
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=28, pady=18)

        status_row = tk.Frame(footer, bg=BG)
        status_row.pack(fill="x", pady=(0, 8))
        tk.Label(status_row, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(side="left")
        tk.Label(status_row, textvariable=self.progress_text, bg=BG, fg=TEXT,
                 font=("TkDefaultFont", 9, "bold")).pack(side="right")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Resolve.Horizontal.TProgressbar",
                        troughcolor=PANEL_2, background=ACCENT,
                        bordercolor=PANEL_2, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=8)
        self.progress = ttk.Progressbar(
            footer, mode="determinate", maximum=100,
            style="Resolve.Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x", pady=(0, 13))

        action_row = tk.Frame(footer, bg=BG)
        action_row.pack(fill="x")
        self._button(action_row, "Open output folder", self.open_output).pack(side="left")
        self.convert_btn = self._button(
            action_row, "Convert videos  →", self.start_conversion, primary=True
        )
        self.convert_btn.pack(side="right")

    def _card(self, parent):
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)

    def _button(self, parent, text, command, primary=False):
        bg = ACCENT if primary else PANEL_2
        fg = "#ffffff" if primary else TEXT
        active = ACCENT_HOVER if primary else "#303444"
        button = tk.Button(
            parent, text=text, command=command, bg=bg, fg=fg,
            activebackground=active, activeforeground="#ffffff",
            relief="flat", bd=0, padx=13, pady=8,
            font=("TkDefaultFont", 10, "bold" if primary else "normal"),
            cursor="hand2", disabledforeground="#6e7282"
        )
        return button

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Choose videos",
            filetypes=[
                ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v"),
                ("All files", "*.*"),
            ],
        )
        self._add_paths(paths)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Choose a folder containing videos")
        if folder:
            paths = sorted(
                str(p) for p in Path(folder).iterdir()
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
            )
            self._add_paths(paths)

    def _add_paths(self, paths):
        existing = {str(p.resolve()) for p in self.files}
        added = 0
        for path in paths:
            p = Path(path).expanduser()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS and str(p.resolve()) not in existing:
                self.files.append(p)
                existing.add(str(p.resolve()))
                self.listbox.insert(tk.END, f"  {p.name}")
                added += 1
        self._update_count()
        if added:
            self.status.set(f"Added {added} video(s). Ready to convert.")
        elif paths:
            self.status.set("No new supported video files were added.")

    def _update_count(self):
        self.file_count.configure(text=f"{len(self.files)} file" + ("" if len(self.files) == 1 else "s"))

    def remove_selected(self):
        indices = list(self.listbox.curselection())
        for index in reversed(indices):
            del self.files[index]
            self.listbox.delete(index)
        self._update_count()

    def clear_files(self):
        if self.is_converting:
            return
        self.files.clear()
        self.listbox.delete(0, tk.END)
        self._update_count()
        self.status.set("File list cleared.")
        self.progress["value"] = 0
        self.progress_text.set("Ready")

    def choose_output(self):
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_dir.set(folder)

    def open_output(self):
        folder = Path(self.output_dir.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror("Could not open folder", str(exc))

    def start_conversion(self):
        if self.is_converting:
            return
        if not self.files:
            messagebox.showinfo("No videos selected", "Add one or more video files first.")
            return
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            messagebox.showerror(
                "FFmpeg is missing",
                "Install FFmpeg first:\n\nsudo pacman -S ffmpeg"
            )
            return
        output = Path(self.output_dir.get()).expanduser()
        if not str(output).strip():
            messagebox.showerror("Choose an output folder", "Select an output folder first.")
            return
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Output folder error", str(exc))
            return

        # Snapshot inputs/settings so the worker has stable values.
        files = list(self.files)
        profile = self.profile.get()
        keep_audio = self.keep_audio.get()
        self.is_converting = True
        self.convert_btn.configure(state="disabled", text="Converting…")
        self.status.set("Preparing conversion…")
        self.progress["value"] = 0
        self.progress_text.set("0%")
        self.worker = threading.Thread(
            target=self._convert_batch,
            args=(files, output, profile, keep_audio),
            daemon=True,
        )
        self.worker.start()

    def _convert_batch(self, files, output_dir, profile, keep_audio):
        success = 0
        skipped = 0
        failed = 0
        for index, source in enumerate(files):
            output = output_dir / f"{source.stem}_resolve.mov"
            if output.resolve() == source.resolve():
                output = output_dir / f"{source.stem}_resolve_converted.mov"

            # Never silently overwrite an existing output.
            if output.exists():
                self.events.put(("overwrite", str(output)))
                # Wait for the UI thread to answer.
                response_queue = queue.Queue()
                self.events.put(("ask_overwrite", (str(output), response_queue)))
                answer = response_queue.get()
                if not answer:
                    skipped += 1
                    self.events.put(("file_skipped", source.name))
                    continue

            result = self._convert_one(
                source, output, profile, keep_audio, index, len(files)
            )
            if result == "success":
                success += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

        self.events.put(("finished", (success, skipped, failed, len(files))))

    def _convert_one(self, source, output, profile, keep_audio, index, total):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(source)],
            capture_output=True, text=True
        )
        if probe.returncode != 0 or "video" not in probe.stdout:
            self.events.put(("error", f"No readable video stream in {source.name}"))
            return "failed"

        profile_map = {
            "DNxHR SQ": ("dnxhr_sq", "yuv422p"),
            "DNxHR HQ": ("dnxhr_hq", "yuv422p"),
            "DNxHR HQX": ("dnxhr_hqx", "yuv422p10le"),
        }
        profile_arg, pixel_format = profile_map[profile]
        command = [
            "ffmpeg", "-hide_banner", "-nostdin", "-y",
            "-i", str(source),
            "-map", "0:v:0",
        ]
        if keep_audio:
            command += ["-map", "0:a:0?"]
        command += [
            "-c:v", "dnxhd",
            "-profile:v", profile_arg,
            "-pix_fmt", pixel_format,
        ]
        if keep_audio:
            command += ["-c:a", "pcm_s16le", "-ar", "48000"]
        else:
            command += ["-an"]
        command += [
            "-progress", "pipe:1", "-nostats",
            str(output),
        ]

        try:
            proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1
            )
            # Drain stderr concurrently to avoid a full pipe blocking FFmpeg.
            stderr_lines = []

            def drain_stderr():
                for line in proc.stderr:
                    stderr_lines.append(line)

            stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
            stderr_thread.start()

            duration = self._duration(source)
            for line in proc.stdout:
                line = line.strip()
                if line.startswith("out_time_ms=") and duration > 0:
                    try:
                        seconds = int(line.split("=", 1)[1]) / 1_000_000
                        file_pct = max(0, min(100, seconds / duration * 100))
                        overall = ((index + file_pct / 100) / total) * 100
                        self.events.put(("progress", (
                            overall, source.name, index + 1, total, file_pct
                        )))
                    except ValueError:
                        pass
                elif line == "progress=end":
                    overall = ((index + 1) / total) * 100
                    self.events.put(("progress", (
                        overall, source.name, index + 1, total, 100
                    )))

            return_code = proc.wait()
            stderr_thread.join(timeout=2)
            if return_code == 0 and output.exists() and output.stat().st_size > 0:
                self.events.put(("file_success", (source.name, str(output))))
                return "success"

            if output.exists():
                try:
                    output.unlink()
                except OSError:
                    pass
            self.events.put(("error", f"FFmpeg failed for {source.name}:\n{''.join(stderr_lines)[-1800:]}"))
            return "failed"
        except OSError as exc:
            self.events.put(("error", f"Could not run FFmpeg for {source.name}: {exc}"))
            return "failed"

    @staticmethod
    def _duration(source):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            capture_output=True, text=True
        )
        try:
            return float(result.stdout.strip())
        except (ValueError, TypeError):
            return 0.0

    def _poll_events(self):
        try:
            while True:
                event, data = self.events.get_nowait()
                if event == "progress":
                    overall, name, current, total, file_pct = data
                    self.progress["value"] = overall
                    self.progress_text.set(f"{overall:.0f}%")
                    self.status.set(f"File {current}/{total}: {name}  ·  {file_pct:.0f}%")
                elif event == "file_success":
                    name, path = data
                    self.status.set(f"Converted: {name}")
                elif event == "file_skipped":
                    self.status.set(f"Skipped existing output for {data}")
                elif event == "error":
                    # Keep the batch running, but show the most recent error.
                    self.status.set(f"Error: {data.splitlines()[0][:100]}")
                    print(data)
                elif event == "ask_overwrite":
                    path, response_queue = data
                    answer = messagebox.askyesno(
                        "Output already exists",
                        f"This output already exists:\n\n{path}\n\nOverwrite it?"
                    )
                    response_queue.put(answer)
                elif event == "finished":
                    success, skipped, failed, total = data
                    self.is_converting = False
                    self.convert_btn.configure(state="normal", text="Convert videos  →")
                    self.progress["value"] = 100 if failed == 0 and success > 0 else self.progress["value"]
                    self.progress_text.set(f"{success}/{total} converted")
                    self.status.set(f"Finished · {success} converted · {skipped} skipped · {failed} failed")
                    messagebox.showinfo(
                        "Conversion finished",
                        f"Converted: {success}\nSkipped: {skipped}\nFailed: {failed}\n\n"
                        f"Output folder:\n{self.output_dir.get()}"
                    )
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _on_close(self):
        if self.is_converting:
            if not messagebox.askyesno(
                "Conversion running",
                "A conversion is running. Close the app anyway? FFmpeg may be interrupted."
            ):
                return
        self.root.destroy()


def main():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("FFmpeg is required. On Arch Linux, install it with: sudo pacman -S ffmpeg")
    root = tk.Tk()
    ResolveReadyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
