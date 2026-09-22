import tempfile
import unittest
from pathlib import Path

from pipeline import Segment, ass_time, clean_text, srt_time, write_srt


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


if __name__ == "__main__":
    unittest.main()
