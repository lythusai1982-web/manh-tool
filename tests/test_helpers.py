import tempfile
import unittest
from pathlib import Path

from pipeline import (
    Segment,
    ass_time,
    clean_text,
    parse_translation_payload,
    srt_time,
    translation_groups,
    translation_payload,
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

    def test_translation_groups_limit_requests(self):
        groups = translation_groups([f"câu {index}" for index in range(17)])
        self.assertEqual([len(group) for group in groups], [8, 8, 1])

    def test_translation_payload_round_trip(self):
        payload = translation_payload(["hello", "how are you"])
        self.assertIn("[[[VSAI0000]]]", payload)
        translated = "[[[VSAI0000]]] xin chào [[[VSAI0001]]] bạn khỏe không"
        self.assertEqual(parse_translation_payload(translated, 2), ["xin chào", "bạn khỏe không"])

    def test_translation_payload_rejects_missing_marker(self):
        self.assertIsNone(parse_translation_payload("chỉ có một câu", 2))


if __name__ == "__main__":
    unittest.main()
