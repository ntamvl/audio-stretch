"""
audio_stretch.models
====================

Định nghĩa các dataclass và enum dùng trong toàn bộ package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StretchMethod(str, Enum):
    """Thuật toán time-stretch được hỗ trợ.

    Attributes:
        RUBBERBAND: Dùng pyrubberband – chất lượng cao, giữ nguyên pitch.
                    Yêu cầu: ``pip install pyrubberband``
        LIBROSA:    Dùng librosa phase-vocoder – không cần thư viện ngoài.
                    Yêu cầu: ``pip install librosa``
        AUTO:       Tự động chọn RUBBERBAND nếu có, fallback sang LIBROSA.
    """

    RUBBERBAND = "rubberband"
    LIBROSA = "librosa"
    AUTO = "auto"


@dataclass
class AudioInfo:
    """Metadata của một file audio.

    Attributes:
        path:         Đường dẫn file.
        sample_rate:  Tần số lấy mẫu (Hz).
        duration_sec: Độ dài (giây).
        channels:     Số kênh (1 = mono, 2 = stereo).
        samples:      Tổng số mẫu.
        dtype:        Kiểu dữ liệu numpy (vd. "float32").
    """

    path: str
    sample_rate: int
    duration_sec: float
    channels: int
    samples: int
    dtype: str

    def __str__(self) -> str:
        return (
            f"AudioInfo(path={self.path!r}, "
            f"duration={self.duration_sec:.3f}s, "
            f"sample_rate={self.sample_rate}Hz, "
            f"channels={self.channels})"
        )


@dataclass
class StretchResult:
    """Kết quả sau khi thực hiện time-stretch.

    Attributes:
        input_path:       File đầu vào.
        output_path:      File đầu ra đã được lưu.
        original_duration: Độ dài gốc (giây).
        actual_duration:  Độ dài thực sau stretch (giây).
        speed_ratio:      Tỉ lệ tốc độ đã áp dụng (>1 nhanh, <1 chậm).
        method:           Thuật toán đã dùng.
        sample_rate:      Sample rate của file đầu ra.
    """

    input_path: str
    output_path: str
    original_duration: float
    actual_duration: float
    speed_ratio: float
    method: StretchMethod
    sample_rate: int

    @property
    def duration_change(self) -> float:
        """Thay đổi độ dài so với gốc (giây, âm = ngắn hơn)."""
        return self.actual_duration - self.original_duration

    @property
    def duration_change_pct(self) -> float:
        """Phần trăm thay đổi so với độ dài gốc."""
        if self.original_duration == 0:
            return 0.0
        return (self.actual_duration - self.original_duration) / self.original_duration * 100

    def __str__(self) -> str:
        direction = "nhanh hơn" if self.speed_ratio > 1 else "chậm hơn" if self.speed_ratio < 1 else "không đổi"
        return (
            f"StretchResult("
            f"{self.original_duration:.3f}s → {self.actual_duration:.3f}s, "
            f"speed={self.speed_ratio:.4f}x [{direction}], "
            f"method={self.method.value})"
        )


@dataclass
class TTSResult:
    """Kết quả sau khi tạo TTS (có hoặc không có stretch).

    Attributes:
        output_path:     File âm thanh đầu ra cuối cùng.
        text:            Văn bản đã được đọc.
        sample_rate:     Sample rate của mô hình TTS.
        tts_duration:    Độ dài audio TTS gốc trước stretch (giây).
        final_duration:  Độ dài audio cuối cùng sau stretch (giây). None nếu không stretch.
        stretch_result:  Chi tiết kết quả stretch, hoặc None nếu không stretch.
    """

    output_path: str
    text: str
    sample_rate: int
    tts_duration: float
    final_duration: Optional[float] = None
    stretch_result: Optional[StretchResult] = None

    @property
    def was_stretched(self) -> bool:
        """True nếu audio đã được stretch sau TTS."""
        return self.stretch_result is not None

    def __str__(self) -> str:
        dur = self.final_duration or self.tts_duration
        stretched = f", stretched={self.final_duration:.3f}s" if self.was_stretched else ""
        return (
            f"TTSResult("
            f"tts={self.tts_duration:.3f}s{stretched}, "
            f"output={self.output_path!r})"
        )
