#!/usr/bin/env python3
"""
ytb_extractor.py — Download audio/video from YouTube using yt-dlp.

Usage:
    uv run ytb_extractor.py <url> [-f mp3|mp4|both] [-o output_name]
        [--from seconds|minutes:seconds] [--to seconds|minutes:seconds]
"""

import argparse
import math
import re
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
    "remote_components": ["ejs:github"],
}


def parse_timestamp(value: str) -> float:
    """Accept non-negative seconds or minutes:seconds (including decimals)."""
    match = re.fullmatch(
        r"(?:(?P<minutes>[0-9]+):)?(?P<seconds>[0-9]+(?:\.[0-9]+)?)",
        value.strip(),
    )
    if match:
        minutes = match.group("minutes")
        seconds = float(match.group("seconds"))
        total = float(minutes or 0) * 60 + seconds
        if math.isfinite(total) and (minutes is None or seconds < 60):
            return total
    raise argparse.ArgumentTypeError(
        "Use non-negative seconds or minutes:seconds (e.g. 90 or 1:30); "
        "the seconds part after ':' must be less than 60."
    )


def get_duration(url: str) -> float | None:
    """Read the duration without downloading media or expanding playlists."""
    opts = {
        **BASE_OPTS,
        "quiet": True,
        "noplaylist": True,
        "extract_flat": "in_playlist",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise ValueError("Could not read media metadata; no media saved.")
    if info.get("_type") in ("playlist", "multi_video"):
        raise ValueError("Time ranges require a single video URL; no media saved.")
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise ValueError("Cannot trim a live or upcoming video; no media saved.")
    return info.get("duration")


def resolve_time_range(
    start: float, end: float | None, duration: float | None
) -> tuple[float, float]:
    """Clamp the end to the duration and reject unknown or empty intervals."""
    if duration is None or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Cannot trim media with an unknown duration; no media saved.")
    if start >= duration:
        raise ValueError(
            f"--from ({start:g}s) must be less than the duration "
            f"({duration:g}s); no media saved."
        )
    effective_end = duration if end is None else min(end, duration)
    if effective_end <= start:
        raise ValueError("--to must be greater than --from; no media saved.")
    return start, effective_end


def build_time_range_opts(time_range: tuple[float, float] | None) -> dict:
    if time_range is None:
        return {}
    return {
        "download_ranges": yt_dlp.utils.download_range_func(None, [time_range]),
        # Re-encoding prevents the cut from drifting to a nearby keyframe.
        "force_keyframes_at_cuts": True,
        "noplaylist": True,
    }


def build_ydl_opts_mp3(
    output_name: str, time_range: tuple[float, float] | None = None
) -> dict:
    return {
        **BASE_OPTS,
        **build_time_range_opts(time_range),
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


def build_ydl_opts_mp4(
    output_name: str, time_range: tuple[float, float] | None = None
) -> dict:
    return {
        **BASE_OPTS,
        **build_time_range_opts(time_range),
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
    parser.add_argument(
        "--from",
        dest="start_time",
        type=parse_timestamp,
        metavar="TIME",
        help="Start at seconds or minutes:seconds (default: 0)",
    )
    parser.add_argument(
        "--to",
        dest="end_time",
        type=parse_timestamp,
        metavar="TIME",
        help="End at seconds or minutes:seconds (default: end of video)",
    )

    args = parser.parse_args()

    time_range = None
    if args.start_time is not None or args.end_time is not None:
        start = args.start_time if args.start_time is not None else 0
        if args.end_time is not None and args.end_time <= start:
            parser.error("--to must be greater than --from; no media saved.")
        try:
            duration = get_duration(args.url)
            time_range = resolve_time_range(start, args.end_time, duration)
        except (ValueError, yt_dlp.utils.DownloadError) as e:
            parser.exit(1, f"Error validating time range: {e}\n")
        if args.end_time is not None and args.end_time > time_range[1]:
            print(
                f"--to ({args.end_time:g}s) exceeds the duration; "
                f"using {time_range[1]:g}s."
            )
        print(f"Time range: {time_range[0]:g}s to {time_range[1]:g}s")

    output_name = args.output if args.output else default_output_name()

    # Sanitize output_name: remove path separators to keep it as a base name
    output_path = Path(output_name)
    if output_path.suffix:
        # User accidentally added an extension — strip it
        output_name = str(output_path.with_suffix(""))

    fmt = args.format

    if fmt in ("mp3", "both"):
        mp3_name = f"{output_name}_audio" if fmt == "both" else output_name
        download(args.url, build_ydl_opts_mp3(mp3_name, time_range), "MP3")

    if fmt in ("mp4", "both"):
        mp4_name = f"{output_name}_video" if fmt == "both" else output_name
        download(args.url, build_ydl_opts_mp4(mp4_name, time_range), "MP4")


if __name__ == "__main__":
    main()
