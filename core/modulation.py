"""
Modulation effects for E-Stim 2B audio signals.

Provides amplitude modulation (AM), frequency modulation (FM),
envelope shaping (ADSR), and other modulation effects that create
dynamic and interesting stimulation patterns.
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModulationType(Enum):
    """Available modulation types."""
    NONE = "none"
    AM = "am"               # Amplitude Modulation
    FM = "fm"               # Frequency Modulation
    PWM = "pwm"             # Pulse Width Modulation
    TREMOLO = "tremolo"     # Rhythmic amplitude variation
    RAMP_UP = "ramp_up"     # Gradual intensity increase
    RAMP_DOWN = "ramp_down" # Gradual intensity decrease
    WAVE = "wave"           # Wave-shaped intensity


@dataclass
class EnvelopeADSR:
    """
    ADSR Envelope for shaping signal amplitude over time.

    attack:  Time in seconds for signal to reach peak
    decay:   Time in seconds to fall from peak to sustain level
    sustain: Amplitude level during sustain phase [0.0, 1.0]
    release: Time in seconds for signal to fade to zero
    """
    attack: float = 0.1
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.2

    def generate(self, duration: float, sample_rate: int = 44100) -> np.ndarray:
        """
        Generate the ADSR envelope.

        If the total duration is shorter than attack+decay+release,
        phases are proportionally scaled.
        """
        num_samples = int(duration * sample_rate)
        envelope = np.zeros(num_samples)

        total_adr = self.attack + self.decay + self.release
        sustain_time = max(0, duration - total_adr)

        # Calculate sample counts for each phase
        if total_adr > duration:
            # Scale phases proportionally
            scale = duration / total_adr
            a_samples = int(self.attack * scale * sample_rate)
            d_samples = int(self.decay * scale * sample_rate)
            s_samples = 0
            r_samples = num_samples - a_samples - d_samples
        else:
            a_samples = int(self.attack * sample_rate)
            d_samples = int(self.decay * sample_rate)
            s_samples = int(sustain_time * sample_rate)
            r_samples = num_samples - a_samples - d_samples - s_samples

        idx = 0

        # Attack: 0 → 1.0
        if a_samples > 0:
            envelope[idx:idx + a_samples] = np.linspace(0, 1.0, a_samples)
            idx += a_samples

        # Decay: 1.0 → sustain
        if d_samples > 0:
            envelope[idx:idx + d_samples] = np.linspace(1.0, self.sustain, d_samples)
            idx += d_samples

        # Sustain
        if s_samples > 0:
            envelope[idx:idx + s_samples] = self.sustain
            idx += s_samples

        # Release: sustain → 0
        if r_samples > 0:
            start_level = self.sustain if s_samples > 0 or d_samples > 0 else (
                envelope[idx - 1] if idx > 0 else 0
            )
            envelope[idx:idx + r_samples] = np.linspace(start_level, 0, r_samples)

        return envelope[:num_samples]


@dataclass
class ModulationParams:
    """Parameters for signal modulation."""
    mod_type: ModulationType = ModulationType.NONE
    rate: float = 1.0           # Modulation rate in Hz
    depth: float = 0.5          # Modulation depth [0.0, 1.0]
    envelope: Optional[EnvelopeADSR] = None

    def __post_init__(self):
        if self.envelope is None:
            self.envelope = EnvelopeADSR()


class Modulator:
    """
    Applies modulation effects to audio signals.

    Works with numpy arrays of float64 samples.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._phase = 0.0            # cumulative sample count
        self._phase_wrapped = 0.0    # wrapped phase for periodic functions
        # Wrap period: 1 second of samples — keeps t values small for sin()
        # while remaining an integer number of samples so t stays continuous.
        self._wrap_period = float(sample_rate)

    def reset_phase(self):
        """Reset modulation phase."""
        self._phase = 0.0
        self._phase_wrapped = 0.0

    def apply(
        self,
        signal: np.ndarray,
        params: ModulationParams,
        continuous: bool = False,
    ) -> np.ndarray:
        """
        Apply modulation to a signal.

        Args:
            signal: Input signal array
            params: Modulation parameters
            continuous: Maintain phase continuity for streaming

        Returns:
            Modulated signal array
        """
        if params.mod_type == ModulationType.NONE:
            return signal.copy()

        num_samples = len(signal) if signal.ndim == 1 else signal.shape[0]

        if continuous:
            # Absolute time (for ramp effects that need to know total elapsed time)
            t_abs = (np.arange(num_samples) + self._phase) / self.sample_rate
            # Wrapped time (for periodic effects — prevents float precision loss)
            t = (np.arange(num_samples) + self._phase_wrapped) / self.sample_rate
            self._phase += num_samples
            self._phase_wrapped = (self._phase_wrapped + num_samples) % self._wrap_period
        else:
            t = np.arange(num_samples) / self.sample_rate
            t_abs = t

        modulator_func = {
            ModulationType.AM: self._am,
            ModulationType.FM: self._fm,
            ModulationType.PWM: self._pwm,
            ModulationType.TREMOLO: self._tremolo,
            ModulationType.RAMP_UP: self._ramp_up,
            ModulationType.RAMP_DOWN: self._ramp_down,
            ModulationType.WAVE: self._wave,
        }

        func = modulator_func.get(params.mod_type)
        if func is None:
            return signal.copy()

        # Ramp effects need absolute time, periodic effects use wrapped time
        if params.mod_type in (ModulationType.RAMP_UP, ModulationType.RAMP_DOWN):
            return func(signal, t_abs, params)
        return func(signal, t, params)

    def apply_envelope(
        self,
        signal: np.ndarray,
        envelope: EnvelopeADSR,
        duration: float,
    ) -> np.ndarray:
        """Apply an ADSR envelope to a signal."""
        env = envelope.generate(duration, self.sample_rate)

        # Handle length mismatch
        num_samples = len(signal) if signal.ndim == 1 else signal.shape[0]
        if len(env) < num_samples:
            env = np.pad(env, (0, num_samples - len(env)))
        elif len(env) > num_samples:
            env = env[:num_samples]

        if signal.ndim == 2:
            return signal * env[:, np.newaxis]
        return signal * env

    def _am(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """Amplitude Modulation."""
        mod = 1.0 - params.depth * (1.0 - np.sin(2 * np.pi * params.rate * t)) / 2.0
        if signal.ndim == 2:
            return signal * mod[:, np.newaxis]
        return signal * mod

    def _fm(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """
        Frequency Modulation - achieved by time-warping the signal.
        For real-time use, this modulates the playback speed.
        """
        num_samples = len(t)
        mod = params.depth * np.sin(2 * np.pi * params.rate * t)
        # Create a modulated time index
        indices = np.arange(num_samples) + mod * self.sample_rate * 0.01
        indices = np.clip(indices, 0, num_samples - 1).astype(int)
        if signal.ndim == 2:
            return signal[indices]
        return signal[indices]

    def _pwm(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """Pulse Width Modulation effect."""
        mod_duty = 0.5 + params.depth * 0.4 * np.sin(2 * np.pi * params.rate * t)
        threshold = 2.0 * mod_duty - 1.0
        if signal.ndim == 2:
            mask_l = np.where(signal[:, 0] > threshold, 1.0, -1.0)
            mask_r = np.where(signal[:, 1] > threshold, 1.0, -1.0)
            return np.column_stack([mask_l, mask_r])
        return np.where(signal > threshold, 1.0, -1.0)

    def _tremolo(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """Tremolo - rhythmic amplitude variation."""
        mod = 1.0 - params.depth * (1.0 + np.sin(2 * np.pi * params.rate * t)) / 2.0
        if signal.ndim == 2:
            return signal * mod[:, np.newaxis]
        return signal * mod

    def _ramp_up(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """Gradual intensity increase.

        Uses absolute time so the ramp progresses across buffers.
        ``rate`` controls the ramp speed: full ramp duration = 1/rate seconds.
        """
        ramp_duration = max(1.0 / max(params.rate, 0.01), 0.1)
        ramp = np.clip(t / ramp_duration, 0.0, 1.0)
        base = 1.0 - params.depth
        mod = base + params.depth * ramp
        if signal.ndim == 2:
            return signal * mod[:, np.newaxis]
        return signal * mod

    def _ramp_down(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """Gradual intensity decrease.

        Uses absolute time so the ramp progresses across buffers.
        ``rate`` controls the ramp speed: full ramp duration = 1/rate seconds.
        """
        ramp_duration = max(1.0 / max(params.rate, 0.01), 0.1)
        ramp = np.clip(1.0 - t / ramp_duration, 0.0, 1.0)
        base = 1.0 - params.depth
        mod = base + params.depth * ramp
        if signal.ndim == 2:
            return signal * mod[:, np.newaxis]
        return signal * mod

    def _wave(self, signal: np.ndarray, t: np.ndarray, params: ModulationParams) -> np.ndarray:
        """Wave-shaped intensity pattern (sine envelope)."""
        mod = 1.0 - params.depth * (1.0 - np.abs(np.sin(np.pi * params.rate * t)))
        if signal.ndim == 2:
            return signal * mod[:, np.newaxis]
        return signal * mod
