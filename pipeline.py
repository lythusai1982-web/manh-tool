from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from offline_engine import OfflineTranslationEngine, ensure_piper_voice

Progress = Callable[[float, str], None]
Logger = Callable[[str], None]


class Cancelled(Exception):
    pass


@dataclass
class Segment:
    start: float
    end: float
    original: str
    vietnamese: str = ""


def srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def ass_time(seconds: float) -> str:
    centis = max(0, round(seconds * 100))
    hours, rest = divmod(centis, 360_000)
    minutes, rest = divmod(rest, 6_000)
    secs, cs = divmod(rest, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def model_root_path() -> Path:
    configured = os.environ.get("VIETSUB_MODEL_DIR")
    if configured:
        return Path(configured)
    public = os.environ.get("PUBLIC")
    if public:
        return Path(public) / "VietsubAI_Runtime" / "models"
    return Path.home() / ".vietsub_ai" / "models"


def write_srt(path: Path, segments: list[Segment]) -> None:
    rows = []
    for index, item in enumerate(segments, 1):
        rows.append(f"{index}\n{srt_time(item.start)} --> {srt_time(item.end)}\n{item.vietnamese}\n")
    path.write_text("\n".join(rows), encoding="utf-8-sig")


def write_ass(path: Path, segments: list[Segment]) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Vietsub,Arial,52,&H00FFFFFF,&H000000FF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,55,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for item in segments:
        text = item.vietnamese.replace("{", "(").replace("}", ")").replace("\n", r"\N")
        events.append(f"Dialogue: 0,{ass_time(item.start)},{ass_time(item.end)},Vietsub,,0,0,0,,{text}")
    path.write_text(header + "\n".join(events), encoding="utf-8-sig")


class VideoTranslator:
    def __init__(self, cancel_event: threading.Event, progress: Progress, log: Logger) -> None:
        import imageio_ffmpeg
        from pydub import AudioSegment

        self.cancel_event = cancel_event
        self.progress = progress
        self.log = log
        self.ffmpeg = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve())
        AudioSegment.converter = self.ffmpeg

    def run(self, source: Path, output_dir: Path, model_name: str, voice: str, make_subtitles: bool, make_dub: bool, mix_original: bool) -> dict[str, Path]:
        from faster_whisper import WhisperModel
        from pydub import AudioSegment

        output_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = re.sub(r"[<>:\"/\\|?*]+", "_", source.stem).strip(" .") or "video"
        final_video = output_dir / f"{safe_stem} - Tieng Viet.mp4"
        final_srt = output_dir / f"{safe_stem} - Vietsub.srt"
        with tempfile.TemporaryDirectory(prefix="vietsub_ai_") as temp_name:
            temp = Path(temp_name)
            audio_wav = temp / "source.wav"
            ass_file = temp / "vietsub.ass"
            dub_wav = temp / "dub.wav"
            mixed_wav = temp / "mixed.wav"

            self._check()
            self.progress(3, "Đang tách âm thanh...")
            self._run_process([self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_wav)])

            self.progress(10, "Đang tải mô hình nhận diện...")
            compute = "int8"
            model_root = model_root_path()
            model_root.mkdir(parents=True, exist_ok=True)
            try:
                model = WhisperModel(
                    model_name,
                    device="cpu",
                    compute_type=compute,
                    download_root=str(model_root),
                )
            except Exception as exc:
                raise RuntimeError(
                    "Không tải hoặc mở được mô hình nhận diện giọng nói. "
                    "Lần đầu sử dụng cần Internet ổn định; hãy kiểm tra mạng rồi bấm lại. "
                    f"Chi tiết: {exc}"
                ) from exc
            self.progress(15, "Đang nhận diện lời nói...")
            raw_segments, info = model.transcribe(str(audio_wav), beam_size=5, vad_filter=True, vad_parameters={"min_silence_duration_ms": 450})
            segments: list[Segment] = []
            duration = max(float(getattr(info, "duration", 0) or 0), 1.0)
            for item in raw_segments:
                self._check()
                text = clean_text(item.text)
                if text:
                    segments.append(Segment(float(item.start), float(item.end), text))
                self.progress(15 + min(25, float(item.end) / duration * 25), "Đang nhận diện lời nói...")
            if not segments:
                raise RuntimeError("Không phát hiện được lời nói rõ ràng trong video.")
            self.log(f"Nhận diện {len(segments)} đoạn, ngôn ngữ: {getattr(info, 'language', 'tự động')}.")

            self._translate(segments, getattr(info, "language", ""))
            write_srt(final_srt, segments)
            write_ass(ass_file, segments)
            self.log(f"Đã tạo Vietsub: {final_srt.name}")

            audio_input: Path | None = None
            if make_dub:
                self._make_dub(segments, audio_wav, dub_wav, voice)
                if mix_original:
                    self.progress(82, "Đang trộn giọng Việt với tiếng gốc...")
                    original = AudioSegment.from_wav(audio_wav) - 19
                    narration = AudioSegment.from_wav(dub_wav) + 2
                    original.overlay(narration).export(mixed_wav, format="wav")
                    audio_input = mixed_wav
                else:
                    audio_input = dub_wav

            self.progress(86, "Đang xuất video MP4...")
            command = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
            if audio_input:
                command += ["-i", str(audio_input)]
            if make_subtitles:
                command += ["-vf", "subtitles=vietsub.ass"]
            command += ["-map", "0:v:0"]
            command += ["-map", "1:a:0"] if audio_input else ["-map", "0:a:0?"]
            command += ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final_video)]
            self._run_process(command, cwd=temp)
            if not final_video.exists() or final_video.stat().st_size < 1024:
                raise RuntimeError("Không tạo được video đầu ra hợp lệ.")
        self.progress(100, "Hoàn tất")
        return {"video": final_video, "subtitles": final_srt}

    def _translate(self, segments: list[Segment], source_language: str) -> None:
        engine = OfflineTranslationEngine(
            model_root=model_root_path(),
            check_cancel=self._check,
            progress=self.progress,
            log=self.log,
        )
        translated = engine.translate(
            [item.original for item in segments], source=source_language, target="vi"
        )
        for item, text in zip(segments, translated):
            item.vietnamese = clean_text(text) or item.original

    def _make_dub(self, segments: list[Segment], source_audio: Path, destination: Path, voice: str) -> None:
        from pydub import AudioSegment
        from pydub.effects import speedup

        from piper import PiperVoice

        self.progress(61, "Đang chuẩn bị giọng Việt ngoại tuyến...")
        voice_model = ensure_piper_voice(
            model_root_path(), self._check, self.progress, self.log
        )
        try:
            piper_voice = PiperVoice.load(str(voice_model))
        except Exception as exc:
            raise RuntimeError(f"Không mở được mô hình giọng Việt ngoại tuyến: {exc}") from exc
        source = AudioSegment.from_wav(source_audio)
        canvas = AudioSegment.silent(duration=len(source), frame_rate=22050)
        with tempfile.TemporaryDirectory(prefix="voice_segments_") as folder_name:
            folder = Path(folder_name)
            for index, item in enumerate(segments):
                self._check()
                wav_path = folder / f"{index:05}.wav"
                try:
                    with wave.open(str(wav_path), "wb") as wav_file:
                        piper_voice.synthesize_wav(item.vietnamese, wav_file)
                except Exception as exc:
                    raise RuntimeError(
                        f"Không tạo được giọng Việt ở đoạn {index + 1}: {exc}"
                    ) from exc
                if not wav_path.is_file() or wav_path.stat().st_size <= 100:
                    raise RuntimeError(f"Giọng Việt ở đoạn {index + 1} không có dữ liệu.")
                clip = AudioSegment.from_wav(wav_path)
                available = max(500, round((item.end - item.start) * 1000) - 80)
                if len(clip) > available:
                    ratio = min(1.80, len(clip) / available)
                    try:
                        clip = speedup(clip, playback_speed=ratio, chunk_size=100, crossfade=20)
                    except Exception:
                        pass
                if len(clip) > available + 700:
                    self.log(f"Đoạn {index + 1} hơi dài; đã rút gọn để giữ đồng bộ.")
                    clip = clip[:available + 700].fade_out(160)
                canvas = canvas.overlay(clip, position=round(item.start * 1000))
                self.progress(67 + (index + 1) / len(segments) * 14, "Đang tạo giọng đọc tiếng Việt trên máy...")
        canvas.export(destination, format="wav")

    def _run_process(self, command: list[str], cwd: Path | None = None) -> None:
        creation_flags = 0x08000000 if __import__("os").name == "nt" else 0
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=creation_flags)
        while process.poll() is None:
            if self.cancel_event.wait(0.2):
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise Cancelled()
        stderr = (process.stderr.read() if process.stderr else b"").decode("utf-8", "replace")
        if process.returncode != 0:
            raise RuntimeError("FFmpeg gặp lỗi: " + (stderr[-800:] or "không rõ nguyên nhân"))

    def _check(self) -> None:
        if self.cancel_event.is_set():
            raise Cancelled()
