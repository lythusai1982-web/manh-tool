import tempfile
import unittest
import zipfile
from pathlib import Path

from offline_engine import find_translation_path, normalise_language_code, safe_extract_archive
from pipeline import (
    Segment,
    ass_time,
    clean_text,
    srt_time,
    write_srt,
)


class HelperTests(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(srt_time(3661.234), "01:01:01,234")

    def test_ass_time(self):
        self.assertEqual(ass_time(61.25), "0:01:01.25")

    def test_clean_text(self):
        self.assertEqual(clean_text("  xin   chào \n bạn "), "xin chào bạn")

    def test_srt_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sub.srt"
            write_srt(path, [Segment(0, 1.5, "hello", "xin chào")])
            value = path.read_text(encoding="utf-8-sig")
            self.assertIn("xin chào", value)
            self.assertIn("00:00:01,500", value)

    @staticmethod
    def package(source, target, version="1.0"):
        return {
            "from_code": source,
            "to_code": target,
            "package_version": version,
            "links": [f"https://argos-net.com/{source}_{target}.argosmodel"],
        }

    def test_translation_prefers_direct_path(self):
        packages = [
            self.package("zh", "en"),
            self.package("en", "vi"),
            self.package("zh", "vi"),
        ]
        path = find_translation_path(packages, "zh", "vi")
        self.assertIsNotNone(path)
        self.assertEqual([(item["from_code"], item["to_code"]) for item in path], [("zh", "vi")])

    def test_translation_can_pivot_through_english(self):
        packages = [self.package("zh", "en"), self.package("en", "vi")]
        path = find_translation_path(packages, "zh", "vi")
        self.assertIsNotNone(path)
        self.assertEqual(
            [(item["from_code"], item["to_code"]) for item in path],
            [("zh", "en"), ("en", "vi")],
        )

    def test_translation_reports_unsupported_path(self):
        self.assertIsNone(find_translation_path([self.package("en", "vi")], "xx", "vi"))

    def test_language_aliases(self):
        self.assertEqual(normalise_language_code("zh-CN"), "zh")
        self.assertEqual(normalise_language_code("fil"), "tl")

    def test_safe_model_extraction_blocks_parent_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "bad.argosmodel"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("../outside.txt", "blocked")
            with self.assertRaises(RuntimeError):
                safe_extract_archive(archive, root / "extract")
            self.assertFalse((root / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
