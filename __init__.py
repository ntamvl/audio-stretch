"""
audio_stretch
=============

Thư viện thay đổi chiều dài âm thanh (time-stretching) mà không mất nội dung,
tích hợp với VoxCPM2 để tạo TTS rồi kiểm soát tốc độ phát.

Public API:
    AudioInfo          – dataclass chứa metadata file audio
    StretchResult      – dataclass chứa kết quả sau khi stretch
    TTSResult          – dataclass chứa kết quả sau khi tạo TTS
    StretchMethod      – enum các thuật toán time-stretch
    AudioStretcher     – class chính để stretch audio
    VoxCPMTTS          – class wrapper VoxCPM2 TTS + stretch
    get_audio_info()   – lấy metadata file audio
    stretch_file()     – hàm tiện ích stretch nhanh

Ví dụ nhanh:
    >>> from audio_stretch import AudioStretcher, stretch_file
    >>> stretch_file("input.wav", "output.wav", duration=10.0)
    >>> stretcher = AudioStretcher(method="rubberband")
    >>> result = stretcher.stretch("input.wav", "output.wav", speed=1.5)
    >>> print(result.actual_duration)
"""

from audio_stretch.models import AudioInfo, StretchResult, TTSResult, StretchMethod
from audio_stretch.core import AudioStretcher
from audio_stretch.tts import VoxCPMTTS
from audio_stretch.utils import get_audio_info, stretch_file

__version__ = "1.0.0"
__author__ = "audio_stretch contributors"
__all__ = [
    # dataclasses / enums
    "AudioInfo",
    "StretchResult",
    "TTSResult",
    "StretchMethod",
    # classes
    "AudioStretcher",
    "VoxCPMTTS",
    # utility functions
    "get_audio_info",
    "stretch_file",
]
