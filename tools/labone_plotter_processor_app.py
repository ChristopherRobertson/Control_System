"""Small desktop/CLI app for processing LabOne Plotter detector exports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from control_app.workflows.labone_plotter_processor import (  # noqa: E402
    DEFAULT_END_WAVENUMBER_CM,
    DEFAULT_START_WAVENUMBER_CM,
    AlignmentMode,
    LabOnePlotterProcessingError,
    process_labone_plotter_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.gui or not args.files:
        return launch_gui(
            start_wavenumber_cm=args.start,
            end_wavenumber_cm=args.end,
            alignment=args.alignment,
            write_txt_copy=not args.no_txt,
        )
    return process_cli(args)


def process_cli(args: argparse.Namespace) -> int:
    failures = 0
    for file_name in args.files:
        try:
            summary = process_labone_plotter_file(
                file_name,
                start_wavenumber_cm=args.start,
                end_wavenumber_cm=args.end,
                alignment=args.alignment,
                write_txt_copy=not args.no_txt,
            )
        except LabOnePlotterProcessingError as exc:
            failures += 1
            print(f"ERROR: {exc}", file=sys.stderr)
            continue
        outputs = ", ".join(str(path) for path in summary.output_paths)
        interpolation = " with detector-2 interpolation" if summary.detector2_interpolated else ""
        print(
            f"Processed {summary.input_path} -> {outputs} "
            f"({summary.data_rows} rows, {summary.alignment_mode_used} alignment{interpolation})"
        )
    return 1 if failures else 0


def launch_gui(
    *,
    start_wavenumber_cm: float = DEFAULT_START_WAVENUMBER_CM,
    end_wavenumber_cm: float = DEFAULT_END_WAVENUMBER_CM,
    alignment: AlignmentMode = "auto",
    write_txt_copy: bool = True,
) -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is required for the desktop file-picker app") from exc

    root = tk.Tk()
    root.title("LabOne Plotter Processor")
    root.geometry("760x520")
    root.minsize(680, 440)

    selected_files: list[str] = []
    start_var = tk.StringVar(value=f"{start_wavenumber_cm:g}")
    end_var = tk.StringVar(value=f"{end_wavenumber_cm:g}")
    alignment_var = tk.StringVar(value=alignment)
    txt_var = tk.BooleanVar(value=write_txt_copy)
    status_var = tk.StringVar(value="No files selected")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    top = ttk.Frame(root, padding=12)
    top.grid(row=0, column=0, sticky="ew")
    top.columnconfigure(1, weight=1)
    top.columnconfigure(3, weight=1)

    ttk.Label(top, text="Start cm^-1").grid(row=0, column=0, sticky="w", padx=(0, 6))
    ttk.Entry(top, textvariable=start_var, width=12).grid(row=0, column=1, sticky="w")
    ttk.Label(top, text="End cm^-1").grid(row=0, column=2, sticky="w", padx=(18, 6))
    ttk.Entry(top, textvariable=end_var, width=12).grid(row=0, column=3, sticky="w")
    ttk.Label(top, text="Alignment").grid(row=0, column=4, sticky="w", padx=(18, 6))
    alignment_box = ttk.Combobox(
        top,
        textvariable=alignment_var,
        values=("auto", "index", "time"),
        width=8,
        state="readonly",
    )
    alignment_box.grid(row=0, column=5, sticky="w")
    ttk.Checkbutton(top, text="TXT copy", variable=txt_var).grid(row=0, column=6, sticky="w", padx=(18, 0))

    files_frame = ttk.Frame(root, padding=(12, 0, 12, 8))
    files_frame.grid(row=1, column=0, sticky="nsew")
    files_frame.columnconfigure(0, weight=1)
    files_frame.rowconfigure(0, weight=1)

    listbox = tk.Listbox(files_frame, activestyle="dotbox")
    listbox.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=listbox.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    listbox.configure(yscrollcommand=scrollbar.set)

    controls = ttk.Frame(root, padding=(12, 0, 12, 8))
    controls.grid(row=2, column=0, sticky="ew")
    controls.columnconfigure(3, weight=1)

    def refresh_file_list() -> None:
        listbox.delete(0, tk.END)
        for file_name in selected_files:
            listbox.insert(tk.END, file_name)
        count = len(selected_files)
        status_var.set(f"{count} file{'s' if count != 1 else ''} selected")

    def add_files() -> None:
        paths = filedialog.askopenfilenames(
            title="Select LabOne Plotter export",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
        )
        for path in paths:
            if path not in selected_files:
                selected_files.append(path)
        refresh_file_list()

    def clear_files() -> None:
        selected_files.clear()
        refresh_file_list()

    ttk.Button(controls, text="Select Files", command=add_files).grid(row=0, column=0, sticky="w")
    ttk.Button(controls, text="Clear", command=clear_files).grid(row=0, column=1, sticky="w", padx=(8, 0))
    process_button = ttk.Button(controls, text="Process")
    process_button.grid(row=0, column=2, sticky="w", padx=(8, 0))
    ttk.Label(controls, textvariable=status_var).grid(row=0, column=3, sticky="e")

    output = tk.Text(root, height=9, wrap="word")
    output.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
    root.rowconfigure(3, weight=0)

    def append_status(message: str) -> None:
        output.insert(tk.END, message + "\n")
        output.see(tk.END)

    def process_selected() -> None:
        if not selected_files:
            messagebox.showwarning("No Files", "Select at least one LabOne Plotter export.")
            return
        try:
            start = float(start_var.get())
            end = float(end_var.get())
        except ValueError:
            messagebox.showerror("Invalid Range", "Start and end wavenumbers must be numbers.")
            return

        process_button.configure(state=tk.DISABLED)
        root.update_idletasks()
        failures = 0
        for file_name in selected_files:
            try:
                summary = process_labone_plotter_file(
                    file_name,
                    start_wavenumber_cm=start,
                    end_wavenumber_cm=end,
                    alignment=alignment_var.get(),  # type: ignore[arg-type]
                    write_txt_copy=txt_var.get(),
                )
            except LabOnePlotterProcessingError as exc:
                failures += 1
                append_status(f"ERROR: {exc}")
                continue
            output_paths = ", ".join(str(path) for path in summary.output_paths)
            interpolation = " with detector-2 interpolation" if summary.detector2_interpolated else ""
            append_status(
                f"Processed {summary.input_path.name}: {summary.data_rows} rows, "
                f"{summary.alignment_mode_used} alignment{interpolation}"
            )
            append_status(f"  {output_paths}")
        process_button.configure(state=tk.NORMAL)
        status_var.set("Done" if failures == 0 else f"Done with {failures} error(s)")

    process_button.configure(command=process_selected)
    refresh_file_list()
    root.mainloop()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert two-trace LabOne Plotter exports into wavenumber/detector tables.",
    )
    parser.add_argument("files", nargs="*", help="LabOne Plotter .txt exports to process")
    parser.add_argument("--gui", action="store_true", help="Open the desktop file-picker app")
    parser.add_argument("--start", type=float, default=DEFAULT_START_WAVENUMBER_CM, help="Start wavenumber")
    parser.add_argument("--end", type=float, default=DEFAULT_END_WAVENUMBER_CM, help="End wavenumber")
    parser.add_argument(
        "--alignment",
        choices=("auto", "index", "time"),
        default="auto",
        help="Trace alignment mode",
    )
    parser.add_argument("--no-txt", action="store_true", help="Only write the .tsv output")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
