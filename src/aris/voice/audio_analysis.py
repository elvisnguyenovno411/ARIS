from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class AudioBlockAnalysis:
    """Chứa mức âm và spectrum suy ra trong RAM cho visualizer cùng VAD."""

    rms: float
    peak: float
    bands: tuple[float, ...]


class AudioBlockAnalyzer:
    """Tính FFT một lần mỗi block để dùng chung cho spectrum và nhận diện transient."""

    def __init__(self, sample_rate: int = 16_000, band_count: int = 24) -> None:
        """Khởi tạo analyzer cùng cache cửa sổ FFT theo kích thước block microphone."""
        self.sample_rate = max(8_000, int(sample_rate))
        self.band_count = max(8, int(band_count))
        self._cached_size = 0
        self._window = np.empty(0, dtype=np.float32)
        self._frequencies = np.empty(0, dtype=np.float64)
        self._band_masks: tuple[np.ndarray, ...] = ()

    def analyze(self, mono: np.ndarray) -> AudioBlockAnalysis:
        """Rút gọn một block mono thành mức âm và phổ mà không giữ raw audio."""
        samples = np.asarray(mono, dtype=np.float32).reshape(-1)
        if samples.size < 8:
            return AudioBlockAnalysis(
                rms=0.0,
                peak=0.0,
                bands=(0.0,) * self.band_count,
            )
        self._prepare_cache(samples.size)
        centered = samples - float(np.mean(samples))
        rms = float(np.sqrt(np.mean(np.square(centered), dtype=np.float64)))
        peak = float(np.max(np.abs(centered)))
        magnitudes = np.abs(np.fft.rfft(centered * self._window)) / samples.size

        bands: list[float] = []
        for mask in self._band_masks:
            magnitude = float(np.max(magnitudes[mask])) if np.any(mask) else 0.0
            decibels = 20.0 * math.log10(magnitude + 1e-7)
            bands.append(max(0.0, min(1.0, (decibels + 70.0) / 52.0)))
        return AudioBlockAnalysis(
            rms=rms,
            peak=peak,
            bands=tuple(bands),
        )

    def _prepare_cache(self, sample_count: int) -> None:
        """Tạo lại cửa sổ, trục tần số và band mask chỉ khi block size thay đổi."""
        if sample_count == self._cached_size:
            return
        self._cached_size = sample_count
        self._window = np.hanning(sample_count).astype(np.float32)
        self._frequencies = np.fft.rfftfreq(sample_count, d=1.0 / self.sample_rate)
        edges = np.geomspace(
            80.0,
            min(5000.0, self.sample_rate / 2),
            self.band_count + 1,
        )
        self._band_masks = tuple(
            (self._frequencies >= low) & (self._frequencies < high)
            for low, high in zip(edges[:-1], edges[1:], strict=True)
        )
