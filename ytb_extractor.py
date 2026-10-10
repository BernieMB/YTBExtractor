#!/usr/bin/env python3
"""
ytb_extractor.py — Download audio/video from YouTube using yt-dlp.

Usage:
    uv run ytb_extractor.py <url> [-f mp3|mp4|both] [-o output_name]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yt_dlp


def default_output_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


BASE_OPTS = {
    "quiet": False,
    "no_warnings": False,
    # Enable remote EJS solver so yt-dlp can handle YouTube JS challenges
    # that are required for some videos (e.g. restricted or newer uploads).
    "extractor_args": {"youtube": {"player_client": ["web_embedded", "android_vr"]}},
    "remote_components": "ejs:github",
}


def build_ydl_opts_mp3(output_name: str) -> dict:
    return {
        **BASE_OPTS,
        "format": "bestaudio/best",
        "outtmpl": f"{output_name}.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }


def build_ydl_opts_mp4(output_name: str) -> dict:
    return {
        **BASE_OPTS,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "outtmpl": f"{output_name}.%(ext)s",
        "merge_output_format": "mp4",
    }


def download(url: str, ydl_opts: dict, label: str) -> None:
    print(f"\n--- Downloading {label} ---")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"--- {label} download complete ---\n")
    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading {label}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract MP3 and/or MP4 from a YouTube URL."
    )
    parser.add_argument("url", help="YouTube page URL")
    parser.add_argument(
        "-f",
        "--format",
        choices=["mp3", "mp4", "both"],
        default="mp3",
        help="Output format: mp3 (default), mp4, or both",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output filename without extension (default: YYYY-MM-DD_HH-MM-SS)",
    )

    args = parser.parse_args()

    output_name = args.output if args.output else default_output_name()

    # Sanitize output_name: remove path separators to keep it as a base name
    output_path = Path(output_name)
    if output_path.suffix:
        # User accidentally added an extension — strip it
        output_name = str(output_path.with_suffix(""))

    fmt = args.format

    if fmt in ("mp3", "both"):
        mp3_name = f"{output_name}_audio" if fmt == "both" else output_name
        download(args.url, build_ydl_opts_mp3(mp3_name), "MP3")

    if fmt in ("mp4", "both"):
        mp4_name = f"{output_name}_video" if fmt == "both" else output_name
        download(args.url, build_ydl_opts_mp4(mp4_name), "MP4")


if __name__ == "__main__":
    main()
