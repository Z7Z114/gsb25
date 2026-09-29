import numpy as np

try:
    import librosa
    import soundfile as sf
    AUDIO_IO_AVAILABLE = True
except Exception:  # librosa / soundfile 是可选重型依赖
    librosa = None
    sf = None
    AUDIO_IO_AVAILABLE = False
from pathlib import Path
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class AudioProcessor:
    """音频处理器：使用librosa去除背景噪音（如风扇声）"""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """加载音频文件"""
        if not AUDIO_IO_AVAILABLE:
            raise RuntimeError("librosa / soundfile 未安装，音频读写不可用（离线环境请勿调用）")
        logger.info(f"加载音频文件: {audio_path}")
        y, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)
        return y, sr

    def remove_background_noise(
        self,
        y: np.ndarray,
        sr: int,
        noise_frame_duration: float = 0.5
    ) -> np.ndarray:
        """
        去除背景噪音（风扇等低频噪音）
        使用谱减法和维纳滤波
        """
        logger.info("开始去除背景噪音...")

        noise_frames = int(noise_frame_duration * sr)
        noise_clip = y[:noise_frames]

        noise_stft = librosa.stft(noise_clip, n_fft=2048, hop_length=512)
        noise_mag = np.mean(np.abs(noise_stft), axis=1, keepdims=True)

        speech_stft = librosa.stft(y, n_fft=2048, hop_length=512)
        speech_mag = np.abs(speech_stft)
        speech_phase = np.angle(speech_stft)

        alpha = 2.0
        beta = 0.01
        clean_mag = np.maximum(speech_mag - alpha * noise_mag, beta * speech_mag)

        clean_stft = clean_mag * np.exp(1j * speech_phase)
        y_clean = librosa.istft(clean_stft, hop_length=512)

        y_clean = librosa.effects.preemphasis(y_clean, coef=0.97)

        y_denoised = self._wiener_filter(y_clean, sr)

        logger.info("背景噪音去除完成")
        return y_denoised

    def _wiener_filter(self, y: np.ndarray, sr: int) -> np.ndarray:
        """维纳滤波进一步降噪"""
        n_fft = 2048
        hop_length = 512

        stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
        mag = np.abs(stft)

        power = mag ** 2
        noise_power = np.mean(power[:, :int(0.5 * sr / hop_length)], axis=1, keepdims=True)
        snr = power / (noise_power + 1e-10)
        gain = snr / (snr + 1)

        enhanced_mag = mag * gain
        enhanced_stft = enhanced_mag * np.exp(1j * np.angle(stft))
        y_enhanced = librosa.istft(enhanced_stft, hop_length=hop_length)

        return y_enhanced

    def process_audio(self, input_path: str, output_path: str = None) -> str:
        """完整的音频处理流程"""
        y, sr = self.load_audio(input_path)

        y_clean = self.remove_background_noise(y, sr)

        if output_path is None:
            input_path_obj = Path(input_path)
            output_path = str(input_path_obj.parent / f"cleaned_{input_path_obj.name}")

        sf.write(output_path, y_clean, sr)
        logger.info(f"处理后的音频已保存至: {output_path}")

        return output_path

    def save_audio(self, y: np.ndarray, sr: int, output_path: str) -> None:
        """保存音频文件"""
        if not AUDIO_IO_AVAILABLE:
            raise RuntimeError("librosa / soundfile 未安装，音频读写不可用（离线环境请勿调用）")
        sf.write(output_path, y, sr)
