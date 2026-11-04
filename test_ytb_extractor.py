import argparse
import contextlib
import functools
import http.server
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from yt_dlp import YoutubeDL
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import DownloadError

import ytb_extractor as extractor


def invoke_main(*args):
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch.object(sys, "argv", ["ytb_extractor.py", *args]),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            extractor.main()
        except SystemExit as error:
            code = error.code
        else:
            code = 0
    return code, stdout.getvalue(), stderr.getvalue()


class TimestampTests(unittest.TestCase):
    def test_supported_formats(self):
        for value, seconds in (
            ("0", 0), ("90", 90), ("1:30", 90), ("1:5", 65),
            ("12:05", 725), ("90:00", 5400), ("90.5", 90.5),
            ("1:30.5", 90.5), (" 0:05 ", 5),
        ):
            with self.subTest(value=value):
                self.assertEqual(extractor.parse_timestamp(value), seconds)

    def test_invalid_formats(self):
        for value in (
            "", "-1", "-1:30", "1:-5", "1:60", "1:99", "1:60.1",
            "1:02:03", "1:", ":30", "abc", "nan", "inf", "1e3",
            "1,5", "1.5:00", "1:2:3:4", "9" * 400,
        ):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    extractor.parse_timestamp(value)


class RangeTests(unittest.TestCase):
    def test_defaults_and_clamping(self):
        for start, end, expected in (
            (30, 90, (30, 90)),
            (0, 60, (0, 60)),
            (90, None, (90, 180)),
            (30, 300, (30, 180)),
            (0, 180, (0, 180)),
            (7, 20, (7, 7.2)),
        ):
            duration = 7.2 if start == 7 else 180
            with self.subTest(start=start, end=end):
                self.assertEqual(
                    extractor.resolve_time_range(start, end, duration), expected
                )

    def test_empty_or_out_of_bounds_ranges(self):
        for start, end in ((200, None), (180, None), (100, 80), (90, 90), (0, 0)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    extractor.resolve_time_range(start, end, 180)

    def test_unusable_duration(self):
        for duration in (None, 0, -1, float("nan"), float("inf")):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "unknown duration"):
                    extractor.resolve_time_range(0, 10, duration)


class DurationTests(unittest.TestCase):
    def test_metadata_does_not_download_media(self):
        with patch.object(extractor.yt_dlp, "YoutubeDL") as ydl_class:
            ydl = ydl_class.return_value.__enter__.return_value
            ydl.extract_info.return_value = {"duration": 180}
            self.assertEqual(extractor.get_duration("test:url"), 180)
            ydl.extract_info.assert_called_once_with("test:url", download=False)
            ydl.download.assert_not_called()

    def test_rejects_non_finite_sources(self):
        for info in (
            None, {"_type": "playlist"}, {"_type": "multi_video"},
            {"is_live": True, "duration": 180}, {"live_status": "is_upcoming"},
        ):
            with self.subTest(info=info):
                with patch.object(extractor.yt_dlp, "YoutubeDL") as ydl_class:
                    ydl = ydl_class.return_value.__enter__.return_value
                    ydl.extract_info.return_value = info
                    with self.assertRaises(ValueError):
                        extractor.get_duration("test:url")
                    ydl.download.assert_not_called()


class CliTests(unittest.TestCase):
    def setUp(self):
        duration_patch = patch.object(extractor, "get_duration", return_value=180)
        download_patch = patch.object(extractor, "download")
        self.duration = duration_patch.start()
        self.download = download_patch.start()
        self.addCleanup(duration_patch.stop)
        self.addCleanup(download_patch.stop)

    def run_cli(self, *args):
        return invoke_main("test:url", "-o", "clip", *args)

    def test_full_download_keeps_existing_behavior(self):
        code, _, error = self.run_cli("-f", "both")
        self.assertEqual(code, 0, error)
        self.duration.assert_not_called()
        self.assertEqual(self.download.call_count, 2)
        for call in self.download.call_args_list:
            self.assertNotIn("download_ranges", call.args[1])
            self.assertNotIn("force_keyframes_at_cuts", call.args[1])

    def test_both_formats_share_the_clamped_range(self):
        code, output, error = self.run_cli("-f", "both", "--from", "1:30", "--to", "300")
        self.assertEqual(code, 0, error)
        self.assertIn("using 180s", output)
        self.duration.assert_called_once()
        self.assertEqual(self.download.call_count, 2)
        for call, name in zip(
            self.download.call_args_list, ("clip_audio", "clip_video"), strict=True
        ):
            opts = call.args[1]
            self.assertEqual(opts["outtmpl"], f"{name}.%(ext)s")
            self.assertEqual(
                list(opts["download_ranges"]({}, None)),
                [{"start_time": 90, "end_time": 180}],
            )
            self.assertTrue(opts["force_keyframes_at_cuts"])

    def test_one_sided_ranges(self):
        for args, expected in (
            (("--from", "1:30"), (90, 180)),
            (("--to", "1:30"), (0, 90)),
            (("--from", "0"), (0, 180)),
        ):
            with self.subTest(args=args):
                code, _, error = self.run_cli(*args)
                self.assertEqual(code, 0, error)
                opts = self.download.call_args.args[1]
                sections = list(opts["download_ranges"]({}, None))
                self.assertEqual(sections, [{"start_time": expected[0], "end_time": expected[1]}])

    def test_invalid_ranges_never_start_either_download(self):
        for args in (
            ("--from", "200"), ("--from", "180"),
            ("--from", "90", "--to", "80"),
            ("--from", "90", "--to", "90"), ("--to", "0"),
            ("--from", "-1"), ("--to", "1:60"),
        ):
            with self.subTest(args=args):
                code, _, error = self.run_cli("-f", "both", *args)
                self.assertNotEqual(code, 0)
                self.assertTrue(error)
                self.download.assert_not_called()

    def test_reversed_range_does_not_need_metadata(self):
        code, _, _ = self.run_cli("--from", "90", "--to", "80")
        self.assertEqual(code, 2)
        self.duration.assert_not_called()
        self.download.assert_not_called()

    def test_unknown_duration_never_downloads(self):
        self.duration.return_value = None
        code, _, error = self.run_cli("-f", "both", "--to", "30")
        self.assertEqual(code, 1)
        self.assertIn("unknown duration", error)
        self.download.assert_not_called()

    def test_metadata_errors_are_reported_without_downloading(self):
        self.duration.side_effect = DownloadError("metadata unavailable")
        code, _, error = self.run_cli("--to", "30")
        self.assertEqual(code, 1)
        self.assertIn("metadata unavailable", error)
        self.download.assert_not_called()


class FixtureIE(InfoExtractor):
    """Local source with known duration and separate video/audio streams."""

    _VALID_URL = r"cliptest:(?P<id>sample)"

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url

    def _real_extract(self, url):
        return {
            "id": "sample",
            "title": "Local eight-second fixture",
            "duration": 8,
            "formats": [
                {
                    "format_id": "video", "url": f"{self.base_url}/video.mp4",
                    "ext": "mp4", "vcodec": "h264", "acodec": "none",
                    "width": 160, "height": 90, "fps": 25,
                },
                {
                    "format_id": "audio", "url": f"{self.base_url}/audio.m4a",
                    "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128,
                },
            ],
        }


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the small fixtures with HTTP byte ranges so FFmpeg can seek."""

    def log_message(self, format, *args):
        pass

    def send_head(self):
        match = re.fullmatch(r"bytes=([0-9]+)-([0-9]*)", self.headers.get("Range", ""))
        path = Path(self.translate_path(self.path))
        if not match or not path.is_file():
            return super().send_head()
        data = path.read_bytes()
        start = int(match[1])
        end = min(int(match[2]) if match[2] else len(data) - 1, len(data) - 1)
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(data)}")
            self.end_headers()
            return None
        content = data[start:end + 1]
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return io.BytesIO(content)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/ffprobe required")
class MediaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ytb range tests ")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        # Red until second 3, blue afterwards. The cut at second 4 is not a keyframe.
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-nostdin", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=160x90:r=25:d=3",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=25:d=5",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
                "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "libx264", "-g", "200",
                "-keyint_min", "200", "-sc_threshold", "0",
                "-movflags", "+faststart", str(cls.root / "video.mp4"),
                "-map", "2:a", "-c:a", "aac", str(cls.root / "audio.m4a"),
            ],
            check=True, capture_output=True, timeout=30,
        )
        handler = functools.partial(QuietHandler, directory=str(cls.root))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def stop_server(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def run_clip(self, name, *args):
        def make_ydl(opts):
            ydl = YoutubeDL({**opts, "quiet": True}, auto_init=False)
            ydl.add_info_extractor(FixtureIE(self.base_url))
            return ydl

        with patch.object(extractor.yt_dlp, "YoutubeDL", side_effect=make_ydl):
            return invoke_main(
                "cliptest:sample", "-o", str(self.root / name), *args
            )

    def assert_media(self, name, expected_duration, expected_streams):
        path = self.root / name
        self.assertTrue(path.is_file(), path)
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration:stream=codec_type", "-of", "json", str(path),
            ],
            check=True, capture_output=True, timeout=15,
        )
        info = json.loads(result.stdout)
        self.assertAlmostEqual(float(info["format"]["duration"]), expected_duration, delta=0.15)
        self.assertEqual({stream["codec_type"] for stream in info["streams"]}, expected_streams)

    def test_both_formats_have_the_requested_duration_and_video_start(self):
        code, output, error = self.run_clip("both", "-f", "both", "--from", "0:04", "--to", "6")
        self.assertEqual(code, 0, output + error)
        self.assert_media("both_audio.mp3", 2, {"audio"})
        self.assert_media("both_video.mp4", 2, {"audio", "video"})
        first_frame = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", str(self.root / "both_video.mp4"),
                "-vf", "scale=1:1", "-frames:v", "1", "-pix_fmt", "rgb24",
                "-f", "rawvideo", "pipe:1",
            ],
            check=True, capture_output=True, timeout=15,
        ).stdout
        self.assertEqual(len(first_frame), 3)
        self.assertGreater(first_frame[2], first_frame[0] + 100, "Cut must start in the blue section")

    def test_clamped_end_reaches_source_end(self):
        code, output, error = self.run_clip("clamped", "-f", "mp4", "--from", "5", "--to", "30")
        self.assertEqual(code, 0, output + error)
        self.assertIn("using 8s", output)
        self.assert_media("clamped.mp4", 3, {"audio", "video"})

    def test_one_sided_ranges_and_full_download(self):
        for name, args, duration in (
            ("from_only", ("--from", "4"), 4),
            ("to_only", ("--to", "2"), 2),
            ("full", (), 8),
        ):
            with self.subTest(name=name):
                code, output, error = self.run_clip(name, "-f", "mp3", *args)
                self.assertEqual(code, 0, output + error)
                self.assert_media(f"{name}.mp3", duration, {"audio"})

    def test_invalid_ranges_leave_no_files(self):
        for index, args in enumerate((
            ("--from", "9"), ("--from", "8"),
            ("--from", "4", "--to", "3"), ("--from", "4", "--to", "4"),
        )):
            name = f"invalid_{index}"
            with self.subTest(args=args):
                code, _, error = self.run_clip(name, "-f", "both", *args)
                self.assertNotEqual(code, 0)
                self.assertIn("no media saved", error)
                self.assertEqual(list(self.root.glob(f"{name}*")), [])


if __name__ == "__main__":
    unittest.main()
