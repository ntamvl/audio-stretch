"""
audio_stretch.tts
=================

Lớp ``VoxCPMTTS`` – wrapper tích hợp VoxCPM2 + AudioStretcher.

Cho phép tạo TTS và kiểm soát tốc độ trong một bước duy nhất,
hoặc dùng riêng lẻ từng bước để linh hoạt hơn.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf

from audio_stretch.core import AudioStretcher
from audio_stretch.models import StretchMethod, StretchResult, TTSResult

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_ID = "openbmb/VoxCPM2"


class VoxCPMTTS:
    """Tạo TTS bằng VoxCPM2 và tuỳ chọn stretch kết quả.

    Mô hình được tải lười (lazy-load) lần đầu khi gọi :meth:`generate`
    hoặc :meth:`generate_array`, giúp import nhanh hơn.

    Args:
        model_id:        Hugging Face model ID. Mặc định ``"openbmb/VoxCPM2"``.
        load_denoiser:   Có tải denoiser không. Mặc định ``False``.
        stretch_method:  Thuật toán time-stretch. Mặc định ``StretchMethod.AUTO``.
        verbose:         In log tiến trình. Mặc định ``True``.

    Examples:
        Tạo TTS rồi stretch về 10 giây::

            from audio_stretch import VoxCPMTTS

            tts = VoxCPMTTS()
            result = tts.generate(
                text="Xin chào, đây là giọng đọc tổng hợp.",
                output_path="output.wav",
                ref_audio="refs/speaker1.wav",
                duration=10.0,
            )
            print(result)

        Dùng lại model đã tải::

            tts = VoxCPMTTS()
            tts.load_model()                    # tải trước, dùng sau

            for text, dur in texts_and_durations:
                tts.generate(text, f"{text[:8]}.wav", duration=dur)
    """

    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        load_denoiser: bool = False,
        stretch_method: StretchMethod | str = StretchMethod.AUTO,
        verbose: bool = True,
    ) -> None:
        self.model_id = model_id
        self.load_denoiser = load_denoiser
        self.verbose = verbose
        self._model = None  # lazy-loaded
        self._stretcher = AudioStretcher(method=stretch_method, verbose=verbose)

    # ─────────────────────────────────────────────
    # Model management
    # ─────────────────────────────────────────────

    def load_model(self) -> None:
        """Tải mô hình VoxCPM2 vào bộ nhớ (nếu chưa tải).

        Gọi hàm này trước khi generate nếu muốn kiểm soát thời điểm tải model,
        hoặc để warm-up trước vòng lặp nhiều câu.
        """
        if self._model is None:
            self._log(f"Đang tải mô hình {self.model_id!r}...")
            from voxcpm import VoxCPM

            self._model = VoxCPM.from_pretrained(
                self.model_id,
                load_denoiser=self.load_denoiser,
            )
            self._log("Tải mô hình xong.")

    @property
    def model(self):
        """Trả về model VoxCPM (tải nếu chưa có)."""
        if self._model is None:
            self.load_model()
        return self._model

    @property
    def sample_rate(self) -> int:
        """Sample rate của mô hình TTS (Hz)."""
        return self.model.tts_model.sample_rate

    # ─────────────────────────────────────────────
    # Public API – generate to file
    # ─────────────────────────────────────────────

    def generate(
        self,
        text: str,
        output_path: str,
        *,
        ref_audio: Optional[str] = None,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10,
        duration: Optional[float] = None,
        speed: Optional[float] = None,
        keep_raw: bool = False,
    ) -> TTSResult:
        """Tạo TTS rồi tuỳ chọn stretch, lưu ra file.

        Args:
            text:                Văn bản cần đọc.
            output_path:         Đường dẫn file audio đầu ra.
            ref_audio:           File WAV tham chiếu giọng đọc (cloning).
            cfg_value:           Classifier-free guidance scale. Mặc định 2.0.
            inference_timesteps: Số bước diffusion. Mặc định 10.
            duration:            Độ dài đích (giây) sau stretch.
                                 Không truyền = không stretch.
            speed:               Tỉ lệ tốc độ sau stretch.
                                 Không truyền = không stretch.
            keep_raw:            Giữ lại file TTS gốc khi có stretch.
                                 Tên file sẽ là ``<output>_raw.wav``.

        Returns:
            :class:`TTSResult` chứa thông tin chi tiết.

        Raises:
            FileNotFoundError: Nếu ``ref_audio`` không tồn tại.
        """
        if ref_audio and not os.path.isfile(ref_audio):
            raise FileNotFoundError(f"Không tìm thấy ref_audio: {ref_audio!r}")

        need_stretch = duration is not None or speed is not None

        # Xác định đường dẫn file TTS gốc
        if need_stretch:
            base, ext = os.path.splitext(output_path)
            raw_path = base + "_raw" + (ext or ".wav")
        else:
            raw_path = output_path

        # Bước 1: TTS
        self._log(f"\n[TTS] {text[:60]!r}{'...' if len(text) > 60 else ''}")
        wav = self._run_tts(text, ref_audio=ref_audio, cfg_value=cfg_value,
                            inference_timesteps=inference_timesteps)
        sr = self.sample_rate
        tts_duration = len(wav) / sr

        self._ensure_dir(raw_path)
        sf.write(raw_path, wav, sr)
        self._log(f"  TTS xong: {tts_duration:.3f}s → {raw_path!r}")

        # Bước 2: Stretch (nếu cần)
        stretch_result: Optional[StretchResult] = None
        if need_stretch:
            self._log(f"\n[Stretch]")
            stretch_result = self._stretcher.stretch(
                raw_path, output_path,
                duration=duration,
                speed=speed,
            )
            if not keep_raw:
                os.remove(raw_path)
                self._log(f"  Xoá file tạm: {raw_path!r}")

        final_duration = stretch_result.actual_duration if stretch_result else tts_duration
        return TTSResult(
            output_path=output_path,
            text=text,
            sample_rate=sr,
            tts_duration=tts_duration,
            final_duration=final_duration,
            stretch_result=stretch_result,
        )

    # ─────────────────────────────────────────────
    # Public API – generate to array
    # ─────────────────────────────────────────────

    def generate_array(
        self,
        text: str,
        *,
        ref_audio: Optional[str] = None,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10,
        duration: Optional[float] = None,
        speed: Optional[float] = None,
    ) -> tuple[np.ndarray, int]:
        """Tạo TTS rồi tuỳ chọn stretch, trả về numpy array (không lưu file).

        Hữu ích khi muốn xử lý tiếp audio trong bộ nhớ trước khi lưu.

        Args:
            text:                Văn bản cần đọc.
            ref_audio:           File WAV tham chiếu giọng đọc.
            cfg_value:           CFG scale. Mặc định 2.0.
            inference_timesteps: Số bước diffusion. Mặc định 10.
            duration:            Độ dài đích (giây) sau stretch.
            speed:               Tỉ lệ tốc độ sau stretch.

        Returns:
            Tuple ``(audio_array, sample_rate)``.

        Examples:
            ::

                import soundfile as sf
                from audio_stretch import VoxCPMTTS

                tts = VoxCPMTTS()
                wav, sr = tts.generate_array(
                    "Xin chào thế giới",
                    ref_audio="refs/speaker1.wav",
                    speed=0.9,
                )
                # Xử lý thêm rồi lưu
                sf.write("final.wav", wav, sr)
        """
        wav = self._run_tts(text, ref_audio=ref_audio, cfg_value=cfg_value,
                            inference_timesteps=inference_timesteps)
        sr = self.sample_rate

        if duration is not None or speed is not None:
            wav, sr = self._stretcher.stretch_array(wav, sr, duration=duration, speed=speed)

        return wav, sr

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    def _run_tts(
        self,
        text: str,
        *,
        ref_audio: Optional[str],
        cfg_value: float,
        inference_timesteps: int,
    ) -> np.ndarray:
        """Gọi VoxCPM model.generate() và trả về numpy array."""
        kwargs: dict = {"text": text}
        if ref_audio:
            kwargs["reference_wav_path"] = ref_audio
        # Chỉ truyền thêm khi khác default để tránh warning
        if cfg_value != 2.0 or inference_timesteps != 10:
            kwargs["cfg_value"] = cfg_value
            kwargs["inference_timesteps"] = inference_timesteps

        return self.model.generate(**kwargs)

    @staticmethod
    def _ensure_dir(path: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
        logger.debug(msg)
