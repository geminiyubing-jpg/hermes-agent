"""Tests for oversized-video compression before Feishu upload (code 9499 fix)."""
from __future__ import annotations

import os
import subprocess
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "plugins"))

pytest.importorskip("lark_oapi")

from platforms.feishu.adapter import FeishuAdapter  # noqa: E402


class TestShrinkVideoForUpload:
    def test_small_file_returns_none_without_ffmpeg(self, tmp_path):
        small = tmp_path / "small.mp4"
        small.write_bytes(b"x" * 1024)
        assert FeishuAdapter._shrink_video_for_upload(str(small)) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert FeishuAdapter._shrink_video_for_upload(str(tmp_path / "nope.mp4")) is None

    def test_no_ffmpeg_returns_none(self, tmp_path):
        big = tmp_path / "big.mp4"
        big.write_bytes(b"x" * (FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES + 1))
        with mock.patch("shutil.which", return_value=None):
            assert FeishuAdapter._shrink_video_for_upload(str(big)) is None

    def test_ffmpeg_failure_returns_none(self, tmp_path):
        big = tmp_path / "big.mp4"
        big.write_bytes(b"x" * (FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES + 1))
        with mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             mock.patch("subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0, stdout="60.0\n"),  # ffprobe duration
                subprocess.CalledProcessError(1, "ffmpeg"),            # ffmpeg fails
            ]
            assert FeishuAdapter._shrink_video_for_upload(str(big)) is None

    def test_ffmpeg_timeout_returns_none(self, tmp_path):
        big = tmp_path / "big.mp4"
        big.write_bytes(b"x" * (FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES + 1))
        with mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             mock.patch("subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0, stdout="60.0\n"),
                subprocess.TimeoutExpired("ffmpeg", 1800),
            ]
            assert FeishuAdapter._shrink_video_for_upload(str(big)) is None

    def test_success_returns_shrunk_path(self, tmp_path):
        big = tmp_path / "big.mp4"
        big.write_bytes(b"x" * (FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES + 1))

        def fake_run(cmd, **kwargs):
            if cmd and cmd[0] == "ffprobe":
                return subprocess.CompletedProcess(cmd, 0, stdout="120.0\n")
            # ffmpeg's output path is the last positional arg
            with open(cmd[-1], "wb") as f:
                f.write(b"x" * (FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES - 1))
            return subprocess.CompletedProcess(cmd, 0)

        with mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             mock.patch("subprocess.run", side_effect=fake_run):
            out = FeishuAdapter._shrink_video_for_upload(str(big))
        assert out and os.path.getsize(out) <= FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES

    def test_empty_ffmpeg_output_returns_none(self, tmp_path):
        big = tmp_path / "big.mp4"
        big.write_bytes(b"x" * (FeishuAdapter._FEISHU_VIDEO_UPLOAD_LIMIT_BYTES + 1))
        with mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
             mock.patch("subprocess.run") as run:
            run.side_effect = [
                subprocess.CompletedProcess([], 0, stdout="60.0\n"),
                subprocess.CompletedProcess([], 0),  # ffmpeg "succeeds" but writes nothing
            ]
            assert FeishuAdapter._shrink_video_for_upload(str(big)) is None
