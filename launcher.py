from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "loi_khoi_dong.txt"


def show_error(message: str) -> None:
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror("Vietsub AI Studio - Lỗi khởi động", message)
        root.destroy()
    except Exception:
        print(message)


def main() -> int:
    os.chdir(ROOT)
    try:
        from app import VietsubApp

        VietsubApp().mainloop()
        return 0
    except Exception as exc:
        details = traceback.format_exc()
        LOG_FILE.write_text(
            f"Thời gian: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"Python: {sys.version}\n"
            f"Thư mục: {ROOT}\n\n{details}",
            encoding="utf-8",
        )
        message = (
            "Tool chưa thể mở vì thiếu hoặc lỗi thư viện.\n\n"
            f"Chi tiết ngắn: {type(exc).__name__}: {exc}\n\n"
            "Hãy chạy lại file Cai_Dat_Va_Chay.bat. "
            "Nếu vẫn lỗi, mở file loi_khoi_dong.txt để xem nguyên nhân."
        )
        show_error(message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
