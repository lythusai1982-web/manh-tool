from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from collections import deque
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


Progress = Callable[[float, str], None]
Logger = Callable[[str], None]
CancelCheck = Callable[[], None]

ARGOS_INDEX_URL = (
    "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
)
ARGOS_DOWNLOAD_HOSTS = {
    "argos-net.com",
    "www.argosopentech.com",
    "argosopentech.nyc3.digitaloceanspaces.com",
}

PIPER_VOICE_NAME = "vi_VN-vais1000-medium"
PIPER_VOICE_FILES = {
    f"{PIPER_VOICE_NAME}.onnx": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"
    ),
    f"{PIPER_VOICE_NAME}.onnx.json": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json"
    ),
}

LANGUAGE_ALIASES = {
    "fil": "tl",
    "iw": "he",
    "jw": "jv",
    "nb": "no",
    "yue": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
}


def normalise_language_code(value: str | None) -> str:
    """Convert language codes returned by speech recognition to Argos codes."""
    code = (value or "").strip().lower().replace("_", "-")
    code = LANGUAGE_ALIASES.get(code, code)
    if "-" in code and code not in LANGUAGE_ALIASES:
        code = code.split("-", 1)[0]
    return LANGUAGE_ALIASES.get(code, code)


def _package_version_key(package: dict) -> tuple[int, ...]:
    value = str(package.get("package_version", "0"))
    numbers = [int(item) for item in re.findall(r"\d+", value)]
    return tuple(numbers) or (0,)


def _translation_packages(packages: Iterable[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for package in packages:
        if package.get("type", "translate") != "translate":
            continue
        source = normalise_language_code(str(package.get("from_code", "")))
        target = normalise_language_code(str(package.get("to_code", "")))
        links = package.get("links")
        if not source or not target or not links:
            continue
        key = (source, target)
        if key not in best or _package_version_key(package) > _package_version_key(best[key]):
            best[key] = package
    return list(best.values())


def find_translation_path(
    packages: Iterable[dict], source: str, target: str = "vi", max_hops: int = 4
) -> list[dict] | None:
    """Return the shortest available package chain, including English pivots."""
    start = normalise_language_code(source)
    finish = normalise_language_code(target)
    if start == finish:
        return []

    graph: dict[str, list[tuple[str, dict]]] = {}
    for package in _translation_packages(packages):
        from_code = normalise_language_code(str(package["from_code"]))
        to_code = normalise_language_code(str(package["to_code"]))
        graph.setdefault(from_code, []).append((to_code, package))

    # Prefer English as the first pivot because the official index has the
    # widest and best-tested coverage through English.
    for edges in graph.values():
        edges.sort(key=lambda edge: (edge[0] != finish, edge[0] != "en", edge[0]))

    queue: deque[tuple[str, list[dict]]] = deque([(start, [])])
    best_depth = {start: 0}
    while queue:
        language, path = queue.popleft()
        if len(path) >= max_hops:
            continue
        for next_language, package in graph.get(language, []):
            next_path = [*path, package]
            if next_language == finish:
                return next_path
            depth = len(next_path)
            if best_depth.get(next_language, max_hops + 1) <= depth:
                continue
            best_depth[next_language] = depth
            queue.append((next_language, next_path))
    return None


def _safe_member_path(name: str) -> PurePosixPath:
    value = name.replace("\\", "/")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise RuntimeError("Gói mô hình có đường dẫn không an toàn.")
    if path.parts and re.match(r"^[A-Za-z]:$", path.parts[0]):
        raise RuntimeError("Gói mô hình có đường dẫn không an toàn.")
    return path


def safe_extract_archive(archive: Path, destination: Path) -> None:
    """Extract a model ZIP without allowing path traversal or symbolic links."""
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            relative = _safe_member_path(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise RuntimeError("Gói mô hình chứa liên kết không an toàn.")
            output = destination.joinpath(*relative.parts)
            if info.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as incoming, output.open("wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)


def _first_link(package: dict) -> str:
    links = package.get("links") or []
    if isinstance(links, str):
        links = [links]
    for link in links:
        parsed = urlparse(str(link))
        if parsed.scheme == "https" and (parsed.hostname or "").lower() in ARGOS_DOWNLOAD_HOSTS:
            return str(link)
    raise RuntimeError("Gói dịch không có liên kết tải chính thức an toàn.")


def _download_file(
    url: str,
    destination: Path,
    check_cancel: CancelCheck,
    progress: Progress,
    progress_start: float,
    progress_span: float,
    label: str,
    maximum_size: int | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    partial.unlink(missing_ok=True)
    request = Request(url, headers={"User-Agent": "Vietsub-AI-Studio/2.0"})
    try:
        with urlopen(request, timeout=90) as response, partial.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0)
            if maximum_size and total > maximum_size:
                raise RuntimeError(f"{label} lớn hơn giới hạn an toàn.")
            downloaded = 0
            while True:
                check_cancel()
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if maximum_size and downloaded > maximum_size:
                    raise RuntimeError(f"{label} lớn hơn giới hạn an toàn.")
                output.write(chunk)
                if total:
                    value = progress_start + min(1.0, downloaded / total) * progress_span
                    progress(value, label)
        if not partial.exists() or partial.stat().st_size == 0:
            raise RuntimeError(f"Không nhận được dữ liệu cho {label.lower()}.")
        os.replace(partial, destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def ensure_piper_voice(
    model_root: Path,
    check_cancel: CancelCheck,
    progress: Progress,
    log: Logger,
) -> Path:
    """Download the Vietnamese Piper voice once and return its ONNX path."""
    voice_root = model_root / "piper" / PIPER_VOICE_NAME
    voice_root.mkdir(parents=True, exist_ok=True)
    model_path = voice_root / f"{PIPER_VOICE_NAME}.onnx"
    config_path = voice_root / f"{PIPER_VOICE_NAME}.onnx.json"

    valid_model = model_path.is_file() and model_path.stat().st_size > 1_000_000
    valid_config = False
    if config_path.is_file() and config_path.stat().st_size > 100:
        try:
            json.loads(config_path.read_text(encoding="utf-8"))
            valid_config = True
        except (OSError, ValueError):
            valid_config = False
    if valid_model and valid_config:
        log("Đang dùng lại giọng Việt ngoại tuyến đã lưu trên máy.")
        return model_path

    log("Lần đầu sử dụng giọng Việt: đang tải mô hình Vais1000 (chỉ một lần).")
    files = list(PIPER_VOICE_FILES.items())
    for index, (filename, url) in enumerate(files):
        target = voice_root / filename
        start = 61 + index * 3
        span = 3
        if filename.endswith(".json"):
            maximum = 2 * 1024 * 1024
        else:
            maximum = 200 * 1024 * 1024
        _download_file(
            url,
            target,
            check_cancel,
            progress,
            start,
            span,
            "Đang tải giọng Việt ngoại tuyến lần đầu...",
            maximum,
        )
    try:
        json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Tệp cấu hình giọng Việt tải về không hợp lệ.") from exc
    if model_path.stat().st_size <= 1_000_000:
        raise RuntimeError("Mô hình giọng Việt tải về không đầy đủ.")
    return model_path


class OfflineTranslationEngine:
    def __init__(
        self,
        model_root: Path,
        check_cancel: CancelCheck,
        progress: Progress,
        log: Logger,
    ) -> None:
        self.root = model_root / "argos"
        self.check_cancel = check_cancel
        self.progress = progress
        self.log = log

    def translate(self, texts: list[str], source: str, target: str = "vi") -> list[str]:
        source_code = normalise_language_code(source)
        target_code = normalise_language_code(target)
        if source_code == target_code:
            self.log("Video đã là tiếng Việt; giữ nguyên nội dung nhận diện.")
            return list(texts)
        if not source_code:
            raise RuntimeError("Không xác định được ngôn ngữ nói trong video.")

        self.progress(42, "Đang chuẩn bị bộ dịch ngoại tuyến...")
        packages = self._load_index()
        path = find_translation_path(packages, source_code, target_code)
        if path is None:
            raise RuntimeError(
                f"Chưa có gói dịch ngoại tuyến từ '{source_code}' sang tiếng Việt. "
                "Hãy thử video có ngôn ngữ khác hoặc chọn mô hình nhận diện chính xác hơn."
            )

        route = [source_code]
        route.extend(normalise_language_code(str(item["to_code"])) for item in path)
        self.log("Tuyến dịch ngoại tuyến: " + " → ".join(route) + ".")

        installed: list[tuple[Path, dict]] = []
        for index, package in enumerate(path):
            start = 42 + (index / max(1, len(path))) * 6
            span = 6 / max(1, len(path))
            installed.append((self._ensure_package(package, start, span), package))

        translated = list(texts)
        for step, (package_dir, package) in enumerate(installed):
            self.check_cancel()
            from_code = normalise_language_code(str(package["from_code"]))
            to_code = normalise_language_code(str(package["to_code"]))
            self.log(f"Đang dịch cục bộ {from_code} → {to_code}...")
            translated = self._translate_step(
                package_dir,
                translated,
                48 + step / max(1, len(installed)) * 12,
                12 / max(1, len(installed)),
            )
        self.progress(60, "Đã dịch xong bằng mô hình ngoại tuyến.")
        return translated

    def _load_index(self) -> list[dict]:
        self.root.mkdir(parents=True, exist_ok=True)
        cache = self.root / "package-index.json"
        if cache.is_file():
            try:
                value = json.loads(cache.read_text(encoding="utf-8"))
                if isinstance(value, list) and value:
                    self.log("Đang dùng danh mục mô hình dịch đã lưu trên máy.")
                    return value
            except (OSError, ValueError):
                cache.unlink(missing_ok=True)

        self.log("Lần đầu sử dụng: đang tải danh mục mô hình dịch (chỉ một lần).")
        try:
            _download_file(
                ARGOS_INDEX_URL,
                cache,
                self.check_cancel,
                self.progress,
                42,
                1,
                "Đang tải danh mục dịch ngoại tuyến lần đầu...",
                10 * 1024 * 1024,
            )
            value = json.loads(cache.read_text(encoding="utf-8"))
        except Exception as exc:
            cache.unlink(missing_ok=True)
            raise RuntimeError(
                "Không tải được danh mục dịch trong lần chạy đầu. "
                "Hãy kiểm tra Internet rồi bấm lại; sau khi tải xong có thể dùng ngoại tuyến. "
                f"Chi tiết: {exc}"
            ) from exc
        if not isinstance(value, list) or not value:
            cache.unlink(missing_ok=True)
            raise RuntimeError("Danh mục mô hình dịch tải về không hợp lệ.")
        return value

    def _ensure_package(self, package: dict, start: float, span: float) -> Path:
        source = normalise_language_code(str(package.get("from_code", "")))
        target = normalise_language_code(str(package.get("to_code", "")))
        version = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(package.get("package_version", "latest")))
        destination = self.root / "packages" / f"{source}_{target}" / version
        if self._valid_package(destination, source, target):
            self.log(f"Đang dùng lại gói dịch {source} → {target} đã lưu trên máy.")
            return destination

        self.log(f"Lần đầu dùng {source} → {target}: đang tải mô hình dịch (chỉ một lần).")
        downloads = self.root / "downloads"
        archive = downloads / f"translate-{source}_{target}-{version}.argosmodel"
        try:
            _download_file(
                _first_link(package),
                archive,
                self.check_cancel,
                self.progress,
                start,
                span,
                f"Đang tải mô hình dịch {source} → {target} lần đầu...",
                600 * 1024 * 1024,
            )
            if not zipfile.is_zipfile(archive):
                raise RuntimeError("Gói mô hình dịch tải về không phải tệp ZIP hợp lệ.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="argos_extract_", dir=destination.parent) as folder:
                extraction_root = Path(folder)
                safe_extract_archive(archive, extraction_root)
                candidates = [item.parent for item in extraction_root.rglob("metadata.json")]
                package_root = next(
                    (item for item in candidates if self._valid_package(item, source, target)),
                    None,
                )
                if package_root is None:
                    raise RuntimeError("Gói mô hình dịch thiếu dữ liệu cần thiết.")
                staging = destination.with_name(destination.name + ".new-" + uuid.uuid4().hex)
                if staging.exists():
                    shutil.rmtree(staging)
                shutil.copytree(package_root, staging)
                if destination.exists():
                    shutil.rmtree(destination)
                os.replace(staging, destination)
        except Exception as exc:
            if isinstance(exc, RuntimeError) and str(exc).startswith("Gói"):
                raise
            raise RuntimeError(
                f"Không tải/cài được mô hình dịch {source} → {target}. "
                f"Hãy kiểm tra Internet rồi thử lại. Chi tiết: {exc}"
            ) from exc
        finally:
            archive.unlink(missing_ok=True)
        return destination

    @staticmethod
    def _valid_package(path: Path, source: str, target: str) -> bool:
        try:
            metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return (
            normalise_language_code(str(metadata.get("from_code", ""))) == source
            and normalise_language_code(str(metadata.get("to_code", ""))) == target
            and (path / "model").is_dir()
            and (path / "sentencepiece.model").is_file()
        )

    def _translate_step(
        self, package_dir: Path, texts: list[str], progress_start: float, progress_span: float
    ) -> list[str]:
        import ctranslate2
        import sentencepiece as spm

        metadata = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8"))
        processor = spm.SentencePieceProcessor(
            model_file=str(package_dir / "sentencepiece.model")
        )
        threads = max(1, min(8, (os.cpu_count() or 4) - 1))
        translator = ctranslate2.Translator(
            str(package_dir / "model"),
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=threads,
        )
        prefix = str(metadata.get("target_prefix", "") or "")

        # Repeated subtitle lines are translated once and then reused.
        unique: list[str] = []
        positions: dict[str, list[int]] = {}
        for index, text in enumerate(texts):
            key = text.strip()
            if key not in positions:
                unique.append(key)
                positions[key] = []
            positions[key].append(index)

        unique_results: dict[str, str] = {}
        batch_size = 16
        for offset in range(0, len(unique), batch_size):
            self.check_cancel()
            batch_text = unique[offset : offset + batch_size]
            tokenized = [processor.encode(item, out_type=str) for item in batch_text]
            target_prefix = [[prefix]] * len(tokenized) if prefix else None
            batches = translator.translate_batch(
                tokenized,
                target_prefix=target_prefix,
                replace_unknowns=True,
                max_batch_size=1024,
                batch_type="tokens",
                beam_size=2,
                num_hypotheses=1,
                length_penalty=0.2,
                return_scores=False,
            )
            for source_text, result in zip(batch_text, batches):
                tokens = list(result.hypotheses[0])
                value = processor.decode_pieces(tokens).replace("▁", " ").replace("_", " ")
                if prefix and value.startswith(prefix):
                    value = value[len(prefix) :]
                unique_results[source_text] = re.sub(r"\s+", " ", value).strip() or source_text
            completed = min(len(unique), offset + len(batch_text))
            self.progress(
                progress_start + completed / max(1, len(unique)) * progress_span,
                "Đang dịch sang tiếng Việt trên máy...",
            )

        output = list(texts)
        for source_text, indexes in positions.items():
            for index in indexes:
                output[index] = unique_results[source_text]
        return output
