# audio-stretch

Thư viện Python để **thay đổi chiều dài âm thanh mà không mất nội dung**, tích hợp sẵn với **VoxCPM2** để tạo TTS và kiểm soát tốc độ phát.

- ⚡ Rút ngắn audio → âm thanh nhanh hơn
- 🐢 Kéo dài audio → âm thanh chậm hơn
- 🎵 Pitch (cao độ) giữ nguyên hoàn toàn
- 🗣️ Tích hợp VoxCPM2 TTS + stretch trong một bước
- 🔧 Dùng được cả dạng thư viện (import) và CLI

---

## Cài đặt

```bash
# Cài đặt cơ bản (chỉ stretch, không có TTS)
pip install audio-stretch

# Với thuật toán chất lượng cao (khuyến nghị)
pip install "audio-stretch[rubberband]"

# Với thuật toán librosa (fallback)
pip install "audio-stretch[librosa]"

# Với TTS VoxCPM2
pip install "audio-stretch[tts]"

# Tất cả tính năng
pip install "audio-stretch[all]"

# Cài đặt từ source
pip install git+https://github.com/ntamvl/audio-stretch

# hoặc
git clone https://github.com/ntamvl/audio-stretch && cd audio-stretch
pip install -e .
# hoặc với dependencies đầy đủ
pip install -e ".[rubberband,tts]"
```

**After installation, quick check:**
```py
python -c "import audio_stretch; print(audio_stretch.__version__)"
```

> **Lưu ý:** `pyrubberband` yêu cầu cài thêm binary `rubberband-cli`:
> ```bash
> # Ubuntu / Debian
> sudo apt install rubberband-cli
> # macOS
> brew install rubberband
> ```

---

## Cấu trúc package

```
audio_stretch/
├── __init__.py     # Public API, re-export tất cả
├── models.py       # AudioInfo, StretchResult, TTSResult, StretchMethod
├── core.py         # AudioStretcher – xử lý time-stretch
├── tts.py          # VoxCPMTTS – wrapper VoxCPM2 + stretch
├── utils.py        # get_audio_info(), stretch_file() – hàm tiện ích
└── cli.py          # CLI entry point (audio-stretch)
```

---

## Hướng dẫn sử dụng dạng thư viện

### 1. Hàm tiện ích nhanh

```python
from audio_stretch import stretch_file, get_audio_info

# ── Xem thông tin file ──────────────────────────────────────────
info = get_audio_info("voice.wav")
print(info)
# AudioInfo(path='voice.wav', duration=7.520s, sample_rate=22050Hz, channels=1)

print(f"Độ dài: {info.duration_sec:.2f}s")
print(f"Sample rate: {info.sample_rate} Hz")

# ── Rút ngắn còn 5 giây (âm thanh nhanh hơn) ───────────────────
result = stretch_file("voice.wav", "voice_fast.wav", duration=5.0)
print(result)
# StretchResult(7.520s → 5.000s, speed=1.5040x [nhanh hơn], method=rubberband)

# ── Kéo dài lên 12 giây (âm thanh chậm hơn) ───────────────────
result = stretch_file("voice.wav", "voice_slow.wav", duration=12.0)

# ── Tăng tốc 1.5 lần ────────────────────────────────────────────
result = stretch_file("voice.wav", "voice_1_5x.wav", speed=1.5)

# ── Làm chậm còn 80% tốc độ ─────────────────────────────────────
result = stretch_file("voice.wav", "voice_0_8x.wav", speed=0.8)

# ── Dùng librosa thay vì rubberband ─────────────────────────────
result = stretch_file("voice.wav", "out.wav", speed=1.2, method="librosa")
```

---

### 2. Class `AudioStretcher` – kiểm soát chi tiết hơn

```python
from audio_stretch import AudioStretcher, StretchMethod

# Khởi tạo một lần, dùng nhiều lần
stretcher = AudioStretcher(
    method=StretchMethod.RUBBERBAND,  # hoặc "rubberband" | "librosa" | "auto"
    verbose=True,                     # in log tiến trình
)

# ── Stretch theo độ dài đích ─────────────────────────────────────
result = stretcher.stretch("input.wav", "output.wav", duration=8.0)
print(f"Tỉ lệ: {result.speed_ratio:.3f}x")
print(f"Thay đổi: {result.duration_change:+.3f}s ({result.duration_change_pct:+.1f}%)")

# ── Stretch theo tỉ lệ tốc độ ───────────────────────────────────
result = stretcher.stretch("input.wav", "output.wav", speed=2.0)

# ── Lấy thông tin file ───────────────────────────────────────────
info = stretcher.get_info("input.wav")
print(info.duration_sec, info.sample_rate)
```

#### Stretch từ numpy array (in-memory)

```python
import soundfile as sf
from audio_stretch import AudioStretcher

data, sr = sf.read("voice.wav")         # đọc vào numpy array

stretcher = AudioStretcher()

# Trả về numpy array (không ghi file)
stretched, sr_out = stretcher.stretch_array(data, sr, speed=1.3)
sf.write("out.wav", stretched, sr_out)

# Hoặc stretch + ghi file, trả về StretchResult
result = stretcher.stretch_and_save_array(data, sr, "out.wav", duration=10.0)
print(result)
```

---

### 3. Class `VoxCPMTTS` – TTS + stretch trong một bước

```python
from audio_stretch import VoxCPMTTS

tts = VoxCPMTTS(
    model_id="openbmb/VoxCPM2",       # mặc định
    load_denoiser=False,               # mặc định
    stretch_method="auto",             # mặc định
    verbose=True,
)

# ── TTS đơn giản (không stretch) ────────────────────────────────
result = tts.generate(
    text="Xin chào, đây là giọng đọc tổng hợp.",
    output_path="output.wav",
    ref_audio="refs/speaker1.wav",
)
print(result)
# TTSResult(tts=7.52s, output='output.wav')

# ── TTS + stretch về đúng 10 giây ───────────────────────────────
result = tts.generate(
    text="Xin chào, đây là giọng đọc tổng hợp.",
    output_path="output.wav",
    ref_audio="refs/speaker1.wav",
    duration=10.0,
)
print(result)
# TTSResult(tts=7.52s, stretched=10.000s, output='output.wav')
print(result.was_stretched)        # True
print(result.stretch_result)       # StretchResult(...)

# ── TTS + tăng tốc 1.2x ─────────────────────────────────────────
result = tts.generate(
    text="Nội dung cần đọc nhanh hơn.",
    output_path="fast.wav",
    ref_audio="refs/speaker1.wav",
    speed=1.2,
)

# ── Giữ lại file TTS gốc (trước stretch) ────────────────────────
result = tts.generate(
    text="Văn bản.",
    output_path="final.wav",
    duration=5.0,
    keep_raw=True,           # lưu thêm file final_raw.wav
)

# ── Tạo nhiều câu, tải model một lần ────────────────────────────
tts.load_model()             # warm-up trước

sentences = [
    ("Câu thứ nhất.", 5.0),
    ("Câu thứ hai dài hơn.", 8.0),
    ("Câu thứ ba ngắn.", 3.0),
]
for i, (text, dur) in enumerate(sentences):
    tts.generate(text, f"out_{i}.wav", ref_audio="refs/speaker1.wav", duration=dur)
```

#### Lấy numpy array thay vì lưu file

```python
import soundfile as sf
from audio_stretch import VoxCPMTTS

tts = VoxCPMTTS()
wav, sr = tts.generate_array(
    "Xin chào thế giới",
    ref_audio="refs/speaker1.wav",
    speed=0.9,
)
# Xử lý tiếp (normalize, mix, …) trước khi lưu
sf.write("final.wav", wav, sr)
```

---

### 4. Sử dụng trực tiếp với VoxCPM (không qua wrapper)

```python
import soundfile as sf
from voxcpm import VoxCPM
from audio_stretch import AudioStretcher

# Tạo TTS bằng VoxCPM trực tiếp
model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
wav = model.generate(
    text="Đây là giọng đọc tổng hợp.",
    reference_wav_path="refs/speaker1.wav",
    cfg_value=2.0,
    inference_timesteps=10,
)
sr = model.tts_model.sample_rate

# Stretch numpy array nhận được từ VoxCPM
stretcher = AudioStretcher()
result = stretcher.stretch_and_save_array(wav, sr, "output.wav", duration=8.0)
print(result)
```

---

### 5. Sử dụng Enum `StretchMethod`

```python
from audio_stretch import StretchMethod, AudioStretcher

# Các giá trị hợp lệ
StretchMethod.AUTO        # tự động (rubberband → librosa)
StretchMethod.RUBBERBAND  # pyrubberband
StretchMethod.LIBROSA     # librosa

# Dùng chuỗi cũng được
stretcher = AudioStretcher(method="rubberband")
stretcher = AudioStretcher(method=StretchMethod.AUTO)
```

---

### 6. Dataclasses trả về

#### `AudioInfo`
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `path` | `str` | Đường dẫn file |
| `sample_rate` | `int` | Tần số lấy mẫu (Hz) |
| `duration_sec` | `float` | Độ dài (giây) |
| `channels` | `int` | Số kênh (1=mono, 2=stereo) |
| `samples` | `int` | Tổng số mẫu |
| `dtype` | `str` | Kiểu dữ liệu numpy |

#### `StretchResult`
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `input_path` | `str` | File đầu vào |
| `output_path` | `str` | File đầu ra |
| `original_duration` | `float` | Độ dài gốc (giây) |
| `actual_duration` | `float` | Độ dài thực sau stretch (giây) |
| `speed_ratio` | `float` | Tỉ lệ tốc độ áp dụng |
| `method` | `StretchMethod` | Thuật toán đã dùng |
| `sample_rate` | `int` | Sample rate đầu ra |
| `duration_change` | `float` | Thay đổi tuyệt đối (giây) |
| `duration_change_pct` | `float` | Thay đổi phần trăm |

#### `TTSResult`
| Thuộc tính | Kiểu | Mô tả |
|---|---|---|
| `output_path` | `str` | File đầu ra cuối cùng |
| `text` | `str` | Văn bản đã đọc |
| `sample_rate` | `int` | Sample rate |
| `tts_duration` | `float` | Độ dài TTS gốc (giây) |
| `final_duration` | `float \| None` | Độ dài sau stretch |
| `stretch_result` | `StretchResult \| None` | Chi tiết stretch |
| `was_stretched` | `bool` | Có stretch không |

---

## Hướng dẫn sử dụng CLI

Sau khi cài đặt, lệnh `audio-stretch` có sẵn trong PATH.

```bash
# Xem help
audio-stretch --help
audio-stretch stretch --help

# Xem thông tin file
audio-stretch info -i voice.wav

# Rút ngắn còn 5 giây
audio-stretch stretch -i voice.wav -o out.wav --duration 5.0

# Kéo dài lên 15 giây
audio-stretch stretch -i voice.wav -o out.wav --duration 15.0

# Tăng tốc 2x
audio-stretch stretch -i voice.wav -o out.wav --speed 2.0

# Làm chậm còn 70%
audio-stretch stretch -i voice.wav -o out.wav --speed 0.7

# Dùng librosa thay rubberband
audio-stretch stretch -i voice.wav -o out.wav --speed 1.3 --method librosa

# TTS đơn giản
audio-stretch tts -t "Xin chào thế giới" -o out.wav --ref-audio refs/speaker1.wav

# TTS + stretch về 10 giây
audio-stretch tts -t "Xin chào" -o out.wav \
    --ref-audio refs/speaker1.wav \
    --duration 10.0

# TTS với style control + tăng tốc
audio-stretch tts \
    -t "(slightly faster, cheerful tone)Xin chào" \
    -o out.wav \
    --ref-audio refs/speaker1.wav \
    --cfg-value 2.0 \
    --inference-timesteps 10 \
    --speed 1.2

# TTS + stretch, giữ lại file TTS gốc
audio-stretch tts -t "Nội dung." -o final.wav --duration 8.0 --keep-raw
```

---

## Logic thay đổi tốc độ

| Tham số | Kết quả |
|---|---|
| `duration` < độ dài gốc | Âm thanh **nhanh** hơn |
| `duration` > độ dài gốc | Âm thanh **chậm** hơn |
| `speed` > 1.0 | Âm thanh **nhanh** hơn |
| `speed` < 1.0 | Âm thanh **chậm** hơn |
| `speed` = 1.0 | Giữ nguyên |

Công thức nội bộ: `rate = original_duration / target_duration`

---

## Yêu cầu hệ thống

| Thư viện | Bắt buộc | Ghi chú |
|---|---|---|
| `soundfile` | ✅ | Đọc/ghi file audio |
| `numpy` | ✅ | Xử lý mảng |
| `pyrubberband` | ⭐ Khuyến nghị | Chất lượng cao, giữ pitch |
| `librosa` | Fallback | Nếu không có rubberband |
| `voxcpm` | Chỉ khi dùng TTS | `VoxCPMTTS` |

Python 3.10+
