"""
audio_stretch.cli
=================

Giao diện dòng lệnh (CLI) cho thư viện audio_stretch.

Entry point được đăng ký trong pyproject.toml:
    [project.scripts]
    audio-stretch = "audio_stretch.cli:main"

Cách dùng:
    audio-stretch info    --input voice.wav
    audio-stretch stretch --input voice.wav --output out.wav --duration 10.0
    audio-stretch stretch --input voice.wav --output out.wav --speed 1.5
    audio-stretch tts     --text "Xin chào" --output out.wav --ref-audio ref.wav
    audio-stretch tts     --text "Xin chào" --output out.wav --duration 8.0
"""

from __future__ import annotations

import argparse
import sys

from audio_stretch.models import StretchMethod


# ─────────────────────────────────────────────
# Sub-command handlers
# ─────────────────────────────────────────────

def cmd_info(args: argparse.Namespace) -> None:
    from audio_stretch.core import AudioStretcher

    stretcher = AudioStretcher(verbose=False)
    info = stretcher.get_info(args.input)

    print("\n📊 Thông tin file audio")
    print("─" * 44)
    print(f"  File        : {info.path}")
    print(f"  Sample rate : {info.sample_rate:,} Hz")
    print(f"  Channels    : {info.channels}")
    print(f"  Duration    : {info.duration_sec:.3f}s")
    print(f"  Samples     : {info.samples:,}")
    print(f"  Data type   : {info.dtype}")
    print()


def cmd_stretch(args: argparse.Namespace) -> None:
    import os

    if not os.path.isfile(args.input):
        _die(f"Không tìm thấy file: {args.input!r}")

    if args.duration is None and args.speed is None:
        _die("Phải truyền --duration hoặc --speed")

    if args.duration is not None and args.speed is not None:
        print("⚠️  Cả --duration và --speed đều được truyền, ưu tiên --duration")

    from audio_stretch.core import AudioStretcher

    print("\n🎛️  Stretch audio")
    print("─" * 44)
    stretcher = AudioStretcher(method=args.method, verbose=True)
    result = stretcher.stretch(
        args.input,
        args.output,
        duration=args.duration,
        speed=args.speed if args.duration is None else None,
    )
    print(f"\n✅ {result}\n")


def cmd_tts(args: argparse.Namespace) -> None:
    import os

    if args.ref_audio and not os.path.isfile(args.ref_audio):
        _die(f"Không tìm thấy ref_audio: {args.ref_audio!r}")

    from audio_stretch.tts import VoxCPMTTS

    print("\n🗣️  Text-to-Speech (VoxCPM2)")
    print("─" * 44)
    tts = VoxCPMTTS(stretch_method=args.method, verbose=True)
    result = tts.generate(
        args.text,
        args.output,
        ref_audio=args.ref_audio,
        cfg_value=args.cfg_value,
        inference_timesteps=args.inference_timesteps,
        duration=args.duration,
        speed=args.speed if args.duration is None else None,
        keep_raw=args.keep_raw,
    )
    print(f"\n✅ {result}\n")


# ─────────────────────────────────────────────
# Parser builder
# ─────────────────────────────────────────────

def _add_stretch_args(parser: argparse.ArgumentParser) -> None:
    """Thêm --duration, --speed, --method dùng chung."""
    parser.add_argument(
        "--duration", "-d", type=float, default=None,
        metavar="SEC",
        help="Độ dài đích (giây). Ngắn hơn → nhanh hơn; dài hơn → chậm hơn.",
    )
    parser.add_argument(
        "--speed", "-s", type=float, default=None,
        metavar="RATIO",
        help="Tỉ lệ tốc độ (>1 nhanh hơn, <1 chậm hơn, =1 không đổi).",
    )
    parser.add_argument(
        "--method",
        choices=[m.value for m in StretchMethod],
        default=StretchMethod.AUTO.value,
        help="Thuật toán time-stretch (mặc định: auto)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio-stretch",
        description="Thay đổi chiều dài âm thanh mà không mất nội dung.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  audio-stretch info -i voice.wav
  audio-stretch stretch -i voice.wav -o out.wav --duration 10.0
  audio-stretch stretch -i voice.wav -o out.wav --speed 1.5
  audio-stretch tts -t "Xin chào" -o out.wav --ref-audio ref.wav --duration 8.0
        """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── info ──────────────────────────────────
    p_info = sub.add_parser("info", help="Xem thông tin file audio")
    p_info.add_argument("--input", "-i", required=True, metavar="FILE",
                        help="File audio cần xem thông tin")

    # ── stretch ───────────────────────────────
    p_stretch = sub.add_parser("stretch", help="Thay đổi tốc độ file audio có sẵn")
    p_stretch.add_argument("--input", "-i", required=True, metavar="FILE")
    p_stretch.add_argument("--output", "-o", required=True, metavar="FILE")
    _add_stretch_args(p_stretch)

    # ── tts ───────────────────────────────────
    p_tts = sub.add_parser("tts", help="Tạo TTS bằng VoxCPM2, tuỳ chọn stretch")
    p_tts.add_argument("--text", "-t", required=True, help="Văn bản cần đọc")
    p_tts.add_argument("--output", "-o", required=True, metavar="FILE")
    p_tts.add_argument("--ref-audio", default=None, metavar="FILE",
                       help="File WAV tham chiếu giọng đọc")
    p_tts.add_argument("--cfg-value", type=float, default=2.0,
                       help="CFG scale (mặc định 2.0)")
    p_tts.add_argument("--inference-timesteps", type=int, default=10,
                       help="Số bước diffusion (mặc định 10)")
    p_tts.add_argument("--keep-raw", action="store_true",
                       help="Giữ lại file TTS gốc trước khi stretch")
    _add_stretch_args(p_tts)

    return parser


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def _die(msg: str, code: int = 1) -> None:
    print(f"❌  {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "info": cmd_info,
        "stretch": cmd_stretch,
        "tts": cmd_tts,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
