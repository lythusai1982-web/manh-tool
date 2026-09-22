from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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


def translation_groups(texts: list[str], max_items: int = 8, max_chars: int = 4200) -> list[list[str]]:
    """Group subtitle lines so one web request can translate several lines safely."""
    groups: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for text in texts:
        marker_chars = 22
        needed = len(text) + marker_chars
        if current and (len(current) >= max_items or current_chars + needed > max_chars):
            groups.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += needed
    if current:
        groups.append(current)
    return groups


def translation_payload(texts: list[str]) -> str:
    return "\n".join(f"[[[VSAI{index:04d}]]] {text}" for index, text in enumerate(texts))


def parse_translation_payload(value: str, expected: int) -> list[str] | None:
    """Split a translated batch. Return None when the service changed our markers."""
    marker = re.compile(r"\[{1,3}\s*VSAI\s*0*(\d+)\s*\]{1,3}", re.IGNORECASE)
    matches = list(marker.finditer(value or ""))
    if len(matches) != expected:
        return None
    result: list[str | None] = [None] * expected
    for position, match in enumerate(matches):
        index = int(match.group(1))
        if index < 0 or index >= expected or result[index] is not None:
            return None
        end = matches[position + 1].start() if position + 1 < len(matches) else len(value)
        translated = clean_text(value[match.end():end])
        if not translated:
            return None
        result[index] = translated
    if any(item is None for item in result):
        return None
    return [item for item in result if item is not None]


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
            model_root = os.environ.get("VIETSUB_MODEL_DIR")
            if not model_root:
                public = os.environ.get("PUBLIC")
                model_root = str(Path(public) / "VietsubAI_Runtime" / "models") if public else None
            model = WhisperModel(model_name, device="cpu", compute_type=compute, download_root=model_root)
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

            self._translate(segments)
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

    def _translate(self, segments: list[Segment]) -> None:
        from deep_translator import GoogleTranslator

        self.progress(42, "Đang dịch sang tiếng Việt...")
        translator = GoogleTranslator(source="auto", target="vi")
        total = len(segments)
        groups = translation_groups([item.original for item in segments])
        self.log(f"Đang dịch {total} đoạn trong {len(groups)} lượt để tránh giới hạn máy chủ.")
        request_state = [0.0]
        completed = 0
        for group_number, texts in enumerate(groups, 1):
            self._check()
            progress_value = 42 + completed / total * 18
            payload = translation_payload(texts)
            translated_text = self._translate_request(
                translator,
                payload,
                request_state,
                progress_value,
                group_number,
                len(groups),
            )
            translated = parse_translation_payload(translated_text, len(texts))
            if translated is None:
                self.log(f"Lượt {group_number}: máy chủ đã đổi dấu tách; chuyển sang chế độ dịch chậm an toàn.")
                translated = []
                for text in texts:
                    translated.append(
                        clean_text(
                            self._translate_request(
                                translator,
                                text,
                                request_state,
                                progress_value,
                                group_number,
                                len(groups),
                            )
                        )
                        or text
                    )

            batch = segments[completed:completed + len(texts)]
            for item, text in zip(batch, translated):
                item.vietnamese = clean_text(text or item.original)
            completed += len(batch)
            self.progress(42 + completed / total * 18, "Đang dịch sang tiếng Việt...")

    def _translate_request(
        self,
        translator: object,
        text: str,
        request_state: list[float],
        progress_value: float,
        group_number: int,
        group_total: int,
    ) -> str:
        """Translate one payload with pacing, cancellation and automatic retries."""
        last_error: Exception | None = None
        for attempt in range(5):
            self._check()
            elapsed = time.monotonic() - request_state[0]
            if elapsed < 0.65:
                self._cancelable_wait(0.65 - elapsed)
            try:
                result = translator.translate(text)  # type: ignore[attr-defined]
                request_state[0] = time.monotonic()
                if not result or not str(result).strip():
                    raise RuntimeError("máy chủ không trả về nội dung")
                return str(result)
            except Exception as exc:
                request_state[0] = time.monotonic()
                last_error = exc
                if attempt == 4:
                    break
                message = f"{type(exc).__name__}: {exc}".lower()
                rate_limited = "toomanyrequests" in message or "too many requests" in message or "429" in message
                waits = (6, 15, 30, 60)
                wait_seconds = waits[attempt] if rate_limited else min(2 * (attempt + 1), 8)
                self.log(
                    f"Lượt dịch {group_number}/{group_total} tạm bị giới hạn; "
                    f"tự thử lại sau {wait_seconds} giây ({attempt + 1}/4)."
                )
                self.progress(progress_value, f"Máy chủ đang bận — tự thử lại sau {wait_seconds} giây...")
                self._cancelable_wait(wait_seconds)
        raise RuntimeError(
            "Dịch vụ dịch đang giới hạn kết nối. Tool đã tự chờ và thử lại nhiều lần. "
            "Hãy đợi khoảng 10 phút rồi chạy lại; không cần cài lại tool. "
            f"Chi tiết: {last_error}"
        )

    def _cancelable_wait(self, seconds: float) -> None:
        deadline = time.monotonic() + max(0.0, seconds)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            if self.cancel_event.wait(min(0.25, remaining)):
                raise Cancelled()

    def _make_dub(self, segments: list[Segment], source_audio: Path, destination: Path, voice: str) -> None:
        from pydub import AudioSegment
        from pydub.effects import speedup

        self.progress(61, "Đang tạo giọng đọc tiếng Việt...")
        source = AudioSegment.from_wav(source_audio)
        canvas = AudioSegment.silent(duration=len(source), frame_rate=24000)
        with tempfile.TemporaryDirectory(prefix="voice_segments_") as folder_name:
            folder = Path(folder_name)
            for index, item in enumerate(segments):
                self._check()
                mp3_path = folder / f"{index:05}.mp3"
                self._tts_with_retry(item.vietnamese, voice, mp3_path)
                clip = AudioSegment.from_file(mp3_path)
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
                self.progress(61 + (index + 1) / len(segments) * 20, "Đang tạo giọng đọc tiếng Việt...")
        canvas.export(destination, format="wav")

    def _tts_with_retry(self, text: str, voice: str, path: Path) -> None:
        import edge_tts

        last_error: Exception | None = None
        for attempt in range(3):
            self._check()
            try:
                asyncio.run(edge_tts.Communicate(text=text, voice=voice, rate="+4%", pitch="+0Hz").save(str(path)))
                if path.exists() and path.stat().st_size > 100:
                    return
            except Exception as exc:
                last_error = exc
                time.sleep(1 + attempt)
        raise RuntimeError(f"Không tạo được giọng đọc: {last_error or 'không có dữ liệu'}")

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
