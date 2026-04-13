"""
audio_stretch.utils
===================

Hàm tiện ích cấp cao – giao diện đơn giản nhất để dùng thư viện.
"""

from __future__ import annotations

from typing import Optional

from audio_stretch.core import AudioStretcher
from audio_stretch.models import AudioInfo, StretchMethod, StretchResult


def get_audio_info(path: str) -> AudioInfo:
    """Lấy metadata của file audio.

    Args:
        path: Đường dẫn file audio (WAV, FLAC, OGG, …).

    Returns:
        :class:`~audio_stretch.models.AudioInfo` chứa thông tin file.

    Raises:
        FileNotFoundError: Nếu file không tồn tại.

    Examples:
        ::

            from audio_stretch import get_audio_info

            info = get_audio_info("voice.wav")
            print(f"Duration: {info.duration_sec:.2f}s, SR: {info.sample_rate}Hz")
    """
    return AudioStretcher(verbose=False).get_info(path)


def stretch_file(
    input_path: str,
    output_path: str,
    *,
    duration: Optional[float] = None,
    speed: Optional[float] = None,
    method: StretchMethod | str = StretchMethod.AUTO,
    verbose: bool = True,
) -> StretchResult:
    """Hàm tiện ích: stretch một file audio rồi lưu.

    Đây là cách nhanh nhất để dùng thư viện mà không cần tạo đối tượng.

    Args:
        input_path:  File audio đầu vào.
        output_path: File audio đầu ra.
        duration:    Độ dài đích (giây).
                     < gốc → nhanh hơn | > gốc → chậm hơn.
        speed:       Tỉ lệ tốc độ (> 1 nhanh, < 1 chậm, = 1 không đổi).
        method:      Thuật toán. ``"auto"`` | ``"rubberband"`` | ``"librosa"``.
        verbose:     In log tiến trình.

    Returns:
        :class:`~audio_stretch.models.StretchResult`.

    Raises:
        FileNotFoundError: Nếu ``input_path`` không tồn tại.
        ValueError:        Nếu không truyền ``duration`` hoặc ``speed``.

    Examples:
        ::

            from audio_stretch import stretch_file

            # Rút ngắn còn 5 giây
            result = stretch_file("voice.wav", "fast.wav", duration=5.0)

            # Tăng tốc 1.5x
            result = stretch_file("voice.wav", "faster.wav", speed=1.5)

            # Làm chậm 0.8x, dùng librosa
            result = stretch_file("voice.wav", "slow.wav", speed=0.8, method="librosa")

            print(result)
    """
    stretcher = AudioStretcher(method=method, verbose=verbose)
    return stretcher.stretch(input_path, output_path, duration=duration, speed=speed)
