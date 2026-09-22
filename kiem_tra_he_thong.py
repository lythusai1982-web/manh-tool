from __future__ import annotations

import platform
import sys
import traceback


MODULES = (
    "pkg_resources",
    "numpy",
    "ctranslate2",
    "faster_whisper",
    "edge_tts",
    "deep_translator",
    "pydub",
    "imageio_ffmpeg",
)


def main() -> int:
    print("Python:", sys.version)
    print("He thong:", platform.platform())
    print("Kien truc:", platform.machine())
    for name in MODULES:
        print(f"Dang kiem tra {name}...", end=" ", flush=True)
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "OK")
            print(version)
        except Exception:
            print("THAT BAI")
            traceback.print_exc()
            return 1

    import ctranslate2
    import imageio_ffmpeg

    print("CTranslate2:", ctranslate2.__version__)
    print("FFmpeg:", imageio_ffmpeg.get_ffmpeg_exe())
    print("TAT CA THANH PHAN: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
