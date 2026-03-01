"""
Waveform generators for E-Stim 2B audio signals.

Provides basic waveform shapes and composite waveforms optimized
for electro-stimulation. All generators produce numpy arrays of
float64 samples in the range [-1.0, 1.0].
"""

import numpy as np
from enum import Enum
from typing import Optional


class WaveformType(Enum):
    """Available waveform types."""
    SINE = "sine"
    SQUARE = "square"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    PULSE = "pulse"
    NOISE = "noise"
    CHIRP = "chirp"
    BURST = "burst"


class WaveformGenerator:
    """
    Generates audio waveforms suitable for E-Stim 2B input.

    All waveforms are generated as numpy arrays with values in [-1.0, 1.0].
    The generator maintains phase continuity for real-time streaming.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._phase = 0.0  # Phase accumulator for continuity

    def reset_phase(self):
        """Reset the phase accumulator."""
        self._phase = 0.0

    def generate(
        self,
        waveform_type: WaveformType,
        frequency: float,
        duration: float = None,
        num_samples: int = None,
        amplitude: float = 1.0,
        duty_cycle: float = 0.5,
        phase_offset: float = 0.0,
        continuous: bool = False,
    ) -> np.ndarray:
        """
        Generate a waveform.

        Args:
            waveform_type: Type of waveform to generate
            frequency: Frequency in Hz
            duration: Duration in seconds (mutually exclusive with num_samples)
            num_samples: Number of samples to generate
            amplitude: Peak amplitude [0.0, 1.0]
            duty_cycle: Duty cycle for pulse waveform [0.0, 1.0]
            phase_offset: Phase offset in radians
            continuous: If True, maintain phase continuity between calls

        Returns:
            numpy array of float64 samples
        """
        if duration is not None:
            num_samples = int(self.sample_rate * duration)
        elif num_samples is None:
            raise ValueError("Either duration or num_samples must be specified")

        # Generate time array with phase continuity
        if continuous:
            t = (np.arange(num_samples) + self._phase) / self.sample_rate
            self._phase += num_samples
        else:
            t = np.arange(num_samples) / self.sample_rate

        phase = 2 * np.pi * frequency * t + phase_offset

        generators = {
            WaveformType.SINE: self._sine,
            WaveformType.SQUARE: self._square,
            WaveformType.TRIANGLE: self._triangle,
            WaveformType.SAWTOOTH: self._sawtooth,
            WaveformType.PULSE: lambda p: self._pulse(p, duty_cycle),
            WaveformType.NOISE: lambda p: self._noise(len(p)),
            WaveformType.CHIRP: lambda p: self._chirp(t, frequency, frequency * 2, duration or num_samples / self.sample_rate),
            WaveformType.BURST: lambda p: self._burst(t, frequency, duty_cycle),
        }

        generator = generators.get(waveform_type)
        if generator is None:
            raise ValueError(f"Unknown waveform type: {waveform_type}")

        signal = generator(phase) * amplitude
        return np.clip(signal, -1.0, 1.0)

    def generate_realtime_block(
        self,
        waveform_type: WaveformType,
        frequency: float,
        num_samples: int,
        amplitude: float = 1.0,
        duty_cycle: float = 0.5,
    ) -> np.ndarray:
        """
        Generate a block of samples for real-time streaming.
        Automatically maintains phase continuity.
        """
        return self.generate(
            waveform_type=waveform_type,
            frequency=frequency,
            num_samples=num_samples,
            amplitude=amplitude,
            duty_cycle=duty_cycle,
            continuous=True,
        )

    # --- Waveform implementations ---

    @staticmethod
    def _sine(phase: np.ndarray) -> np.ndarray:
        """Pure sine wave."""
        return np.sin(phase)

    @staticmethod
    def _square(phase: np.ndarray) -> np.ndarray:
        """Square wave."""
        return np.sign(np.sin(phase))

    @staticmethod
    def _triangle(phase: np.ndarray) -> np.ndarray:
        """Triangle wave."""
        return 2.0 * np.abs(2.0 * (phase / (2 * np.pi) % 1.0) - 1.0) - 1.0

    @staticmethod
    def _sawtooth(phase: np.ndarray) -> np.ndarray:
        """Sawtooth wave."""
        return 2.0 * (phase / (2 * np.pi) % 1.0) - 1.0

    @staticmethod
    def _pulse(phase: np.ndarray, duty_cycle: float) -> np.ndarray:
        """Pulse wave with variable duty cycle."""
        normalized = phase / (2 * np.pi) % 1.0
        return np.where(normalized < duty_cycle, 1.0, -1.0)

    @staticmethod
    def _noise(num_samples: int) -> np.ndarray:
        """White noise."""
        return np.random.uniform(-1.0, 1.0, num_samples)

    @staticmethod
    def _chirp(t: np.ndarray, freq_start: float, freq_end: float, duration: float) -> np.ndarray:
        """Frequency sweep (chirp) from freq_start to freq_end."""
        if duration <= 0:
            duration = 1.0
        k = (freq_end - freq_start) / duration
        phase = 2 * np.pi * (freq_start * t + 0.5 * k * t ** 2)
        return np.sin(phase)

    @staticmethod
    def _burst(t: np.ndarray, frequency: float, duty_cycle: float) -> np.ndarray:
        """
        Burst pattern - periodic bursts of sine waves.
        duty_cycle controls the on/off ratio of the burst envelope.
        """
        burst_freq = frequency / 10  # Burst rate is 1/10 of carrier
        envelope = np.where((burst_freq * t % 1.0) < duty_cycle, 1.0, 0.0)
        carrier = np.sin(2 * np.pi * frequency * t)
        return carrier * envelope


class StereoWaveformGenerator:
    """
    Stereo waveform generator for E-Stim 2B dual channel output.

    Left channel  → E-Stim Channel A
    Right channel → E-Stim Channel B
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.channel_a = WaveformGenerator(sample_rate)
        self.channel_b = WaveformGenerator(sample_rate)

    def reset_phase(self):
        """Reset phase on both channels."""
        self.channel_a.reset_phase()
        self.channel_b.reset_phase()

    def generate_stereo(
        self,
        # Channel A (Left) parameters
        waveform_a: WaveformType = WaveformType.SINE,
        frequency_a: float = 100.0,
        amplitude_a: float = 1.0,
        duty_cycle_a: float = 0.5,
        # Channel B (Right) parameters
        waveform_b: WaveformType = WaveformType.SINE,
        frequency_b: float = 100.0,
        amplitude_b: float = 1.0,
        duty_cycle_b: float = 0.5,
        # Common parameters
        duration: float = None,
        num_samples: int = None,
        continuous: bool = False,
    ) -> np.ndarray:
        """
        Generate stereo audio with independent channel control.

        Returns:
            numpy array of shape (num_samples, 2) - column 0 = left/A, column 1 = right/B
        """
        left = self.channel_a.generate(
            waveform_type=waveform_a,
            frequency=frequency_a,
            duration=duration,
            num_samples=num_samples,
            amplitude=amplitude_a,
            duty_cycle=duty_cycle_a,
            continuous=continuous,
        )
        right = self.channel_b.generate(
            waveform_type=waveform_b,
            frequency=frequency_b,
            duration=duration,
            num_samples=num_samples,
            amplitude=amplitude_b,
            duty_cycle=duty_cycle_b,
            continuous=continuous,
        )

        return np.column_stack([left, right])

    def generate_stereo_block(
        self,
        num_samples: int,
        waveform_a: WaveformType = WaveformType.SINE,
        frequency_a: float = 100.0,
        amplitude_a: float = 1.0,
        duty_cycle_a: float = 0.5,
        waveform_b: WaveformType = WaveformType.SINE,
        frequency_b: float = 100.0,
        amplitude_b: float = 1.0,
        duty_cycle_b: float = 0.5,
    ) -> np.ndarray:
        """Generate a stereo block for real-time streaming."""
        return self.generate_stereo(
            waveform_a=waveform_a,
            frequency_a=frequency_a,
            amplitude_a=amplitude_a,
            duty_cycle_a=duty_cycle_a,
            waveform_b=waveform_b,
            frequency_b=frequency_b,
            amplitude_b=amplitude_b,
            duty_cycle_b=duty_cycle_b,
            num_samples=num_samples,
            continuous=True,
        )
