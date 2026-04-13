"""
audio_stretch.core
==================

Lớp ``AudioStretcher`` – thành phần trung tâm thực hiện time-stretching.

Hỗ trợ hai backend:
    - pyrubberband  (chất lượng cao, giữ pitch, khuyến nghị)
    - librosa       (phase-vocoder, không cần binary ngoài)
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf

from audio_stretch.models import AudioInfo, StretchMethod, StretchResult

logger = logging.getLogger(__name__)


class AudioStretcher:
    """Thực hiện time-stretching trên file audio hoặc numpy array.

    Time-stretching thay đổi tốc độ phát mà **không** thay đổi pitch (cao độ),
    do đó nội dung âm thanh được giữ nguyên hoàn toàn.

    Args:
        method:  Thuật toán time-stretch. Mặc định ``StretchMethod.AUTO``.
        verbose: In log tiến trình ra stdout. Mặc định ``True``.

    Examples:
        Stretch theo độ dài đích::

            from audio_stretch import AudioStretcher

            stretcher = AudioStretcher()
            result = stretcher.stretch("input.wav", "output.wav", duration=10.0)
            print(result)

        Stretch theo tỉ lệ tốc độ::

            result = stretcher.stretch("input.wav", "output.wav", speed=1.5)

        Stretch trực tiếp từ numpy array::

            import soundfile as sf
            data, sr = sf.read("input.wav")
            stretched, sr_out = stretcher.stretch_array(data, sr, speed=0.8)
    """

    def __init__(
        self,
        method: StretchMethod | str = StretchMethod.AUTO,
        verbose: bool = True,
    ) -> None:
        if isinstance(method, str):
            method = StretchMethod(method)
        self.method = method
        self.verbose = verbose
        self._resolved_method: Optional[StretchMethod] = None  # set khi thực sự dùng

    # ─────────────────────────────────────────────
    # Public API – file-based
    # ─────────────────────────────────────────────

    def stretch(
        self,
        input_path: str,
        output_path: str,
        *,
        duration: Optional[float] = None,
        speed: Optional[float] = None,
    ) -> StretchResult:
        """Stretch file audio và lưu kết quả.

        Phải truyền đúng **một** trong ``duration`` hoặc ``speed``.
        Nếu truyền cả hai, ``duration`` được ưu tiên.

        Args:
            input_path:  Đường dẫn file audio đầu vào.
            output_path: Đường dẫn file audio đầu ra.
            duration:    Độ dài mong muốn (giây).
                         < độ dài gốc → âm thanh **nhanh** hơn.
                         > độ dài gốc → âm thanh **chậm** hơn.
            speed:       Tỉ lệ tốc độ.
                         > 1 → nhanh hơn (vd. 1.5 = nhanh 1.5 lần).
                         < 1 → chậm hơn (vd. 0.5 = chậm 2 lần).

        Returns:
            :class:`StretchResult` chứa thông tin chi tiết.

        Raises:
            FileNotFoundError: Nếu ``input_path`` không tồn tại.
            ValueError:        Nếu tham số không hợp lệ.
        """
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"Không tìm thấy file audio: {input_path!r}")

        data, sr = sf.read(input_path, always_2d=False)
        original_duration = len(data) / sr
        rate = self._resolve_rate(original_duration, duration=duration, speed=speed)

        self._log(f"Stretch: {input_path!r}")
        self._log(f"  Độ dài gốc  : {original_duration:.3f}s")
        if duration is not None:
            self._log(f"  Độ dài đích : {duration:.3f}s")
        direction = "nhanh hơn" if rate > 1 else "chậm hơn" if rate < 1 else "không đổi"
        self._log(f"  Tỉ lệ tốc độ: {rate:.4f}x [{direction}]")

        stretched = self._do_stretch(data, sr, rate)
        self._ensure_dir(output_path)
        sf.write(output_path, stretched, sr)

        actual_duration = len(stretched) / sr
        self._log(f"  Độ dài thực : {actual_duration:.3f}s → {output_path!r}")

        return StretchResult(
            input_path=input_path,
            output_path=output_path,
            original_duration=original_duration,
            actual_duration=actual_duration,
            speed_ratio=rate,
            method=self._resolved_method or self.method,
            sample_rate=sr,
        )

    def get_info(self, path: str) -> AudioInfo:
        """Trả về metadata của file audio.

        Args:
            path: Đường dẫn file audio.

        Returns:
            :class:`AudioInfo` chứa thông tin file.

        Raises:
            FileNotFoundError: Nếu file không tồn tại.
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Không tìm thấy file: {path!r}")

        data, sr = sf.read(path, always_2d=False)
        duration = len(data) / sr
        channels = data.shape[1] if data.ndim > 1 else 1
        return AudioInfo(
            path=path,
            sample_rate=sr,
            duration_sec=duration,
            channels=channels,
            samples=len(data),
            dtype=str(data.dtype),
        )

    # ─────────────────────────────────────────────
    # Public API – array-based
    # ─────────────────────────────────────────────

    def stretch_array(
        self,
        data: np.ndarray,
        sample_rate: int,
        *,
        duration: Optional[float] = None,
        speed: Optional[float] = None,
    ) -> tuple[np.ndarray, int]:
        """Stretch trực tiếp từ numpy array (không cần đọc/ghi file).

        Hữu ích khi dữ liệu audio đã có trong bộ nhớ (vd. sau khi VoxCPM generate).

        Args:
            data:        Numpy array âm thanh (1D mono hoặc 2D [samples, channels]).
            sample_rate: Sample rate (Hz).
            duration:    Độ dài mong muốn (giây).
            speed:       Tỉ lệ tốc độ.

        Returns:
            Tuple ``(stretched_array, sample_rate)``.

        Raises:
            ValueError: Nếu tham số không hợp lệ.

        Examples:
            ::

                import soundfile as sf
                from audio_stretch import AudioStretcher

                data, sr = sf.read("voice.wav")
                stretched, sr = AudioStretcher().stretch_array(data, sr, speed=0.8)
                sf.write("slow.wav", stretched, sr)
        """
        original_duration = len(data) / sample_rate
        rate = self._resolve_rate(original_duration, duration=duration, speed=speed)
        stretched = self._do_stretch(data, sample_rate, rate)
        return stretched, sample_rate

    def stretch_and_save_array(
        self,
        data: np.ndarray,
        sample_rate: int,
        output_path: str,
        *,
        duration: Optional[float] = None,
        speed: Optional[float] = None,
    ) -> StretchResult:
        """Stretch từ numpy array rồi lưu ra file.

        Thường dùng sau khi nhận ``wav`` từ ``model.generate()`` của VoxCPM.

        Args:
            data:        Numpy array âm thanh.
            sample_rate: Sample rate (Hz).
            output_path: Đường dẫn file đầu ra.
            duration:    Độ dài mong muốn (giây).
            speed:       Tỉ lệ tốc độ.

        Returns:
            :class:`StretchResult`.

        Examples:
            ::

                from voxcpm import VoxCPM
                from audio_stretch import AudioStretcher

                model = VoxCPM.from_pretrained("openbmb/VoxCPM2")
                wav = model.generate(text="Hello", reference_wav_path="ref.wav")
                sr  = model.tts_model.sample_rate

                result = AudioStretcher().stretch_and_save_array(
                    wav, sr, "output.wav", duration=8.0
                )
                print(result)
        """
        original_duration = len(data) / sample_rate
        rate = self._resolve_rate(original_duration, duration=duration, speed=speed)

        self._log(f"Stretch array → {output_path!r}")
        direction = "nhanh hơn" if rate > 1 else "chậm hơn" if rate < 1 else "không đổi"
        self._log(f"  {original_duration:.3f}s → rate={rate:.4f}x [{direction}]")

        stretched = self._do_stretch(data, sample_rate, rate)
        self._ensure_dir(output_path)
        sf.write(output_path, stretched, sample_rate)

        actual_duration = len(stretched) / sample_rate
        self._log(f"  Độ dài thực : {actual_duration:.3f}s")

        return StretchResult(
            input_path="<array>",
            output_path=output_path,
            original_duration=original_duration,
            actual_duration=actual_duration,
            speed_ratio=rate,
            method=self._resolved_method or self.method,
            sample_rate=sample_rate,
        )

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    @staticmethod
    def _resolve_rate(
        original_duration: float,
        *,
        duration: Optional[float],
        speed: Optional[float],
    ) -> float:
        """Tính tỉ lệ tốc độ từ duration hoặc speed."""
        if duration is not None:
            if duration <= 0:
                raise ValueError(f"duration phải > 0, nhận được {duration}")
            return original_duration / duration
        if speed is not None:
            if speed <= 0:
                raise ValueError(f"speed phải > 0, nhận được {speed}")
            return speed
        raise ValueError("Phải truyền duration hoặc speed")

    def _do_stretch(self, data: np.ndarray, sr: int, rate: float) -> np.ndarray:
        """Dispatch tới backend phù hợp."""
        method = self.method
        if method == StretchMethod.AUTO:
            method = self._detect_method()

        if method == StretchMethod.RUBBERBAND:
            result = self._stretch_rubberband(data, sr, rate)
            self._resolved_method = StretchMethod.RUBBERBAND
        else:
            result = self._stretch_librosa(data, sr, rate)
            self._resolved_method = StretchMethod.LIBROSA
        return result

    def _detect_method(self) -> StretchMethod:
        """Kiểm tra pyrubberband có thể dùng không, nếu không thì dùng librosa."""
        try:
            import pyrubberband  # noqa: F401
            return StretchMethod.RUBBERBAND
        except ImportError:
            self._log("  [auto] pyrubberband không có, dùng librosa")
            return StretchMethod.LIBROSA

    @staticmethod
    def _stretch_rubberband(data: np.ndarray, sr: int, rate: float) -> np.ndarray:
        import pyrubberband as pyrb

        data_f64 = data.astype("float64")
        if data_f64.ndim == 1:
            return pyrb.time_stretch(data_f64, sr, rate).astype("float32")

        channels = [
            pyrb.time_stretch(data_f64[:, c], sr, rate)
            for c in range(data_f64.shape[1])
        ]
        return np.stack(channels, axis=1).astype("float32")

    @staticmethod
    def _stretch_librosa(data: np.ndarray, sr: int, rate: float) -> np.ndarray:
        try:
            import librosa
        except ImportError as exc:
            raise ImportError(
                "Cần cài ít nhất một trong: pyrubberband hoặc librosa.\n"
                "  pip install pyrubberband   # khuyến nghị\n"
                "  pip install librosa        # fallback"
            ) from exc

        data_f32 = data.astype("float32")
        if data_f32.ndim == 1:
            return librosa.effects.time_stretch(data_f32, rate=rate)

        channels = [
            librosa.effects.time_stretch(data_f32[:, c], rate=rate)
            for c in range(data_f32.shape[1])
        ]
        return np.stack(channels, axis=1)

    @staticmethod
    def _ensure_dir(path: str) -> None:
        """Tạo thư mục cha nếu chưa tồn tại."""
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
        logger.debug(msg)
