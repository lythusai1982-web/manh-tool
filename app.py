from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, DISABLED, END, NORMAL, X, BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk

from pipeline import Cancelled, VideoTranslator


class VietsubApp(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Vietsub AI Studio")
        self.geometry("790x650")
        self.minsize(700, 600)
        self.configure(bg="#f4f7fb")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()

        self.video_path = StringVar()
        self.output_dir = StringVar(value=str(Path.home() / "Videos" / "Vietsub AI"))
        self.model = StringVar(value="small")
        self.voice = StringVar(value="Ngoại tuyến — Vais1000")
        self.mode = StringVar(value="Vietsub + giọng Việt")
        self.keep_original = BooleanVar(value=True)
        self.status = StringVar(value="Sẵn sàng")
        self.percent = StringVar(value="0%")

        self._styles()
        self._ui()
        self.after(100, self._poll)

    def _styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f7fb")
        style.configure("Card.TFrame", background="white")
        style.configure("Title.TLabel", background="#f4f7fb", foreground="#15213a", font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background="#f4f7fb", foreground="#66738b", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="white", foreground="#1c2942", font=("Segoe UI", 10))
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 11), background="#6c4cff", foreground="white")
        style.map("Primary.TButton", background=[("active", "#5639dd"), ("disabled", "#b9b1df")])
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Horizontal.TProgressbar", troughcolor="#e8eaf2", background="#6c4cff", thickness=12)

    def _ui(self) -> None:
        outer = ttk.Frame(self, padding=24)
        outer.pack(fill=BOTH, expand=True)
        ttk.Label(outer, text="Dịch video thành tiếng Việt", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Nhận diện • dịch • giọng Việt chạy cục bộ, không giới hạn lượt", style="Sub.TLabel").pack(anchor="w", pady=(3, 18))

        card = ttk.Frame(outer, style="Card.TFrame", padding=20)
        card.pack(fill=BOTH, expand=True)
        ttk.Label(card, text="Video cần dịch", style="Card.TLabel").pack(anchor="w")
        file_row = ttk.Frame(card, style="Card.TFrame")
        file_row.pack(fill=X, pady=(7, 14))
        self.file_entry = ttk.Entry(file_row, textvariable=self.video_path)
        self.file_entry.pack(side="left", fill=X, expand=True, ipady=7)
        self.file_button = ttk.Button(file_row, text="Chọn video", command=self._choose_video)
        self.file_button.pack(side="left", padx=(8, 0))

        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill=X)
        for column in range(3):
            row.columnconfigure(column, weight=1)
        ttk.Label(row, text="Kết quả", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(row, text="Giọng đọc", style="Card.TLabel").grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(row, text="Độ chính xác", style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(8, 0))
        self.mode_box = ttk.Combobox(row, textvariable=self.mode, state="readonly", values=("Vietsub + giọng Việt", "Chỉ Vietsub", "Chỉ giọng Việt"))
        self.mode_box.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(7, 14), ipady=5)
        self.voice_box = ttk.Combobox(
            row,
            textvariable=self.voice,
            state="readonly",
            values=("Ngoại tuyến — Vais1000",),
        )
        self.voice_box.grid(row=1, column=1, sticky="ew", padx=8, pady=(7, 14), ipady=5)
        self.model_box = ttk.Combobox(row, textvariable=self.model, state="readonly", values=("base", "small", "medium"))
        self.model_box.grid(row=1, column=2, sticky="ew", padx=(8, 0), pady=(7, 14), ipady=5)

        ttk.Label(card, text="Thư mục xuất", style="Card.TLabel").pack(anchor="w")
        out_row = ttk.Frame(card, style="Card.TFrame")
        out_row.pack(fill=X, pady=(7, 8))
        self.out_entry = ttk.Entry(out_row, textvariable=self.output_dir)
        self.out_entry.pack(side="left", fill=X, expand=True, ipady=6)
        self.out_button = ttk.Button(out_row, text="Chọn...", command=self._choose_output)
        self.out_button.pack(side="left", padx=(8, 0))
        self.mix_check = ttk.Checkbutton(card, variable=self.keep_original, text="Giữ tiếng gốc nhỏ phía sau giọng Việt (tự nhiên hơn)")
        self.mix_check.pack(anchor="w", pady=(2, 15))

        status_row = ttk.Frame(card, style="Card.TFrame")
        status_row.pack(fill=X)
        ttk.Label(status_row, textvariable=self.status, style="Card.TLabel").pack(side="left")
        ttk.Label(status_row, textvariable=self.percent, style="Card.TLabel").pack(side="right")
        self.progress = ttk.Progressbar(card, maximum=100)
        self.progress.pack(fill=X, pady=(7, 15))

        buttons = ttk.Frame(card, style="Card.TFrame")
        buttons.pack(fill=X)
        self.start_button = ttk.Button(buttons, text="BẮT ĐẦU DỊCH", style="Primary.TButton", command=self._start)
        self.start_button.pack(side="left", fill=X, expand=True)
        self.cancel_button = ttk.Button(buttons, text="Hủy", state=DISABLED, command=self._cancel)
        self.cancel_button.pack(side="left", padx=(9, 0))
        ttk.Button(buttons, text="Mở thư mục", command=self._open_output).pack(side="left", padx=(9, 0))

        self.log = __import__("tkinter").Text(card, height=7, bg="#f7f8fc", fg="#556178", relief="flat", font=("Consolas", 9), wrap="word")
        self.log.pack(fill=BOTH, expand=True, pady=(15, 0))
        self._log("Lần đầu dùng một ngôn ngữ/giọng đọc, mô hình sẽ được tải về máy.")
        self._log("Sau khi tải xong, phần dịch và giọng Việt chạy ngoại tuyến, không giới hạn lượt.")
        self._log("Chỉ xử lý video bạn sở hữu hoặc được phép sử dụng.")

    def _choose_video(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v"), ("Tất cả tệp", "*.*")])
        if path:
            self.video_path.set(path)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(path).parent / "Vietsub AI"))

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(initialdir=self.output_dir.get())
        if path:
            self.output_dir.set(path)

    def _start(self) -> None:
        source = Path(self.video_path.get().strip())
        if not source.is_file():
            messagebox.showwarning("Chưa chọn video", "Hãy chọn một tệp video hợp lệ.")
            return
        output = Path(self.output_dir.get()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Không thể lưu", str(exc))
            return
        values = (source, output, self.model.get(), "vais1000", self.mode.get(), self.keep_original.get())
        self.cancel_event.clear()
        self.progress["value"] = 0
        self.percent.set("0%")
        self._busy(True)
        threading.Thread(target=self._work, args=values, daemon=True).start()

    def _work(self, source: Path, output: Path, model: str, voice: str, mode: str, mix_original: bool) -> None:
        try:
            worker = VideoTranslator(self.cancel_event, self._progress_event, self._log_event)
            result = worker.run(
                source=source,
                output_dir=output,
                model_name=model,
                voice=voice,
                make_subtitles=mode != "Chỉ giọng Việt",
                make_dub=mode != "Chỉ Vietsub",
                mix_original=mix_original,
            )
            self.events.put(("done", result))
        except Cancelled:
            self.events.put(("cancelled", None))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _progress_event(self, value: float, text: str) -> None:
        self.events.put(("progress", (value, text)))

    def _log_event(self, text: str) -> None:
        self.events.put(("log", text))

    def _poll(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    pct, text = value  # type: ignore[misc]
                    self.progress["value"] = pct
                    self.percent.set(f"{pct:.0f}%")
                    self.status.set(text)
                elif kind == "log":
                    self._log(str(value))
                elif kind == "done":
                    self._busy(False)
                    result = value  # type: ignore[assignment]
                    self.progress["value"] = 100
                    self.percent.set("100%")
                    self.status.set("Hoàn tất")
                    self._log(f"Đã tạo: {result['video']}")
                    messagebox.showinfo("Đã hoàn thành", "Video tiếng Việt và tệp Vietsub đã được tạo xong.")
                elif kind == "cancelled":
                    self._busy(False)
                    self.status.set("Đã hủy")
                    self._log("Đã hủy theo yêu cầu.")
                elif kind == "error":
                    self._busy(False)
                    self.status.set("Có lỗi")
                    self._log("Lỗi: " + str(value))
                    messagebox.showerror("Không xử lý được", str(value))
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status.set("Đang hủy...")
        self.cancel_button.configure(state=DISABLED)

    def _busy(self, busy: bool) -> None:
        state = DISABLED if busy else NORMAL
        for item in (self.file_entry, self.file_button, self.out_entry, self.out_button, self.mix_check, self.start_button):
            item.configure(state=state)
        for item in (self.mode_box, self.voice_box, self.model_box):
            item.configure(state="disabled" if busy else "readonly")
        self.cancel_button.configure(state=NORMAL if busy else DISABLED)

    def _open_output(self) -> None:
        path = Path(self.output_dir.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _log(self, text: str) -> None:
        self.log.configure(state=NORMAL)
        self.log.insert(END, text.rstrip() + "\n")
        self.log.see(END)
        self.log.configure(state=DISABLED)


if __name__ == "__main__":
    VietsubApp().mainloop()
