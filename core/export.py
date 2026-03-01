"""
WAV file export for E-Stim 2B audio sessions.

Exports sessions and individual waveforms to WAV files that can be
played through the E-Stim 2B audio input.
"""

import numpy as np
import os
from typing import Optional

try:
    from scipy.io import wavfile
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from .waveforms import WaveformType, StereoWaveformGenerator
from .modulation import Modulator, ModulationParams, EnvelopeADSR
from .patterns import PatternSegment, TransitionType
from .session import Session


class AudioExporter:
    """Export audio to WAV files."""

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.generator = StereoWaveformGenerator(sample_rate)
        self.modulator_a = Modulator(sample_rate)
        self.modulator_b = Modulator(sample_rate)

    def export_segment(self, segment: PatternSegment, filepath: str):
        """Export a single segment to a WAV file."""
        audio = self._render_segment(segment)
        self._write_wav(filepath, audio)

    def export_session(
        self,
        session: Session,
        filepath: str,
        progress_callback=None,
    ):
        """
        Export an entire session to a WAV file.

        Args:
            session: The session to export
            filepath: Output WAV file path
            progress_callback: Optional callback(progress: float) with 0.0 - 1.0
        """
        if not session.segments:
            raise ValueError("Session hat keine Segmente")

        blocks = []
        total_segments = len(session.segments)

        for i, segment in enumerate(session.segments):
            # Render segment
            audio = self._render_segment(segment)

            # Apply transition with previous segment
            if i > 0 and blocks:
                prev_segment = session.segments[i - 1]
                audio = self._apply_transition(
                    blocks[-1], audio,
                    prev_segment.transition,
                    prev_segment.transition_duration,
                )
                blocks[-1] = audio[:0]  # Clear previous (merged into transition)
                blocks.append(audio)
            else:
                blocks.append(audio)

            if progress_callback:
                progress_callback((i + 1) / total_segments)

        # Concatenate all blocks
        full_audio = np.concatenate([b for b in blocks if len(b) > 0], axis=0)

        # Apply master volume
        full_audio *= session.master_volume

        # Clip
        np.clip(full_audio, -1.0, 1.0, out=full_audio)

        self._write_wav(filepath, full_audio)

    def _render_segment(self, segment: PatternSegment) -> np.ndarray:
        """Render a segment to a stereo numpy array."""
        self.generator.reset_phase()
        self.modulator_a.reset_phase()
        self.modulator_b.reset_phase()

        # Generate base stereo signal
        stereo = self.generator.generate_stereo(
            waveform_a=segment.channel_a.waveform,
            frequency_a=segment.channel_a.frequency,
            amplitude_a=segment.channel_a.amplitude,
            duty_cycle_a=segment.channel_a.duty_cycle,
            waveform_b=segment.channel_b.waveform,
            frequency_b=segment.channel_b.frequency,
            amplitude_b=segment.channel_b.amplitude,
            duty_cycle_b=segment.channel_b.duty_cycle,
            duration=segment.duration,
        )

        # Apply modulation to Channel A
        if segment.modulation_a.mod_type != ModulationParams().mod_type or \
           segment.modulation_a.mod_type.value != "none":
            mod_a = segment.modulation_a
            if mod_a.mod_type.value != "none":
                stereo[:, 0] = self.modulator_a.apply(stereo[:, 0], mod_a)

        # Apply modulation to Channel B
        if segment.modulation_b.mod_type != ModulationParams().mod_type or \
           segment.modulation_b.mod_type.value != "none":
            mod_b = segment.modulation_b
            if mod_b.mod_type.value != "none":
                stereo[:, 1] = self.modulator_b.apply(stereo[:, 1], mod_b)

        # Apply ADSR envelope
        if segment.use_envelope:
            env = segment.envelope.generate(segment.duration, self.sample_rate)
            if len(env) == stereo.shape[0]:
                stereo[:, 0] *= env
                stereo[:, 1] *= env

        return stereo

    def _apply_transition(
        self,
        prev_audio: np.ndarray,
        next_audio: np.ndarray,
        transition: TransitionType,
        duration: float,
    ) -> np.ndarray:
        """Apply transition effect between two audio segments."""
        transition_samples = int(duration * self.sample_rate)

        if transition == TransitionType.INSTANT or transition_samples == 0:
            return np.concatenate([prev_audio, next_audio], axis=0)

        if transition == TransitionType.CROSSFADE:
            return self._crossfade(prev_audio, next_audio, transition_samples)

        if transition == TransitionType.FADE_OUT_IN:
            return self._fade_out_in(prev_audio, next_audio, transition_samples)

        return np.concatenate([prev_audio, next_audio], axis=0)

    def _crossfade(self, prev: np.ndarray, next_audio: np.ndarray, samples: int) -> np.ndarray:
        """Crossfade between two audio segments."""
        samples = min(samples, len(prev), len(next_audio))

        if samples <= 0:
            return np.concatenate([prev, next_audio], axis=0)

        # Fade curves
        fade_out = np.linspace(1.0, 0.0, samples)
        fade_in = np.linspace(0.0, 1.0, samples)

        # Apply crossfade
        result_start = prev[:-samples]
        crossfade_region = (
            prev[-samples:] * fade_out[:, np.newaxis] +
            next_audio[:samples] * fade_in[:, np.newaxis]
        )
        result_end = next_audio[samples:]

        return np.concatenate([result_start, crossfade_region, result_end], axis=0)

    def _fade_out_in(self, prev: np.ndarray, next_audio: np.ndarray, samples: int) -> np.ndarray:
        """Fade out previous, silence gap, fade in next."""
        half = samples // 2
        half = min(half, len(prev), len(next_audio))

        if half <= 0:
            return np.concatenate([prev, next_audio], axis=0)

        # Fade out the end of previous
        fade_out = np.linspace(1.0, 0.0, half)
        prev_copy = prev.copy()
        prev_copy[-half:] *= fade_out[:, np.newaxis]

        # Fade in the start of next
        fade_in = np.linspace(0.0, 1.0, half)
        next_copy = next_audio.copy()
        next_copy[:half] *= fade_in[:, np.newaxis]

        # Small silence gap
        gap = np.zeros((int(self.sample_rate * 0.05), 2))

        return np.concatenate([prev_copy, gap, next_copy], axis=0)

    def _write_wav(self, filepath: str, audio: np.ndarray):
        """Write audio data to WAV file."""
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

        if HAS_SCIPY:
            # Convert to 16-bit PCM
            audio_16bit = (audio * 32767).astype(np.int16)
            wavfile.write(filepath, self.sample_rate, audio_16bit)
        else:
            # Fallback: manual WAV writing
            self._write_wav_manual(filepath, audio)

    def _write_wav_manual(self, filepath: str, audio: np.ndarray):
        """Write WAV file without scipy."""
        import struct

        audio_16bit = (audio * 32767).astype(np.int16)
        num_channels = audio_16bit.shape[1] if audio_16bit.ndim == 2 else 1
        num_samples = audio_16bit.shape[0]
        bytes_per_sample = 2
        data_size = num_samples * num_channels * bytes_per_sample

        with open(filepath, 'wb') as f:
            # RIFF header
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + data_size))
            f.write(b'WAVE')

            # Format chunk
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))  # Chunk size
            f.write(struct.pack('<H', 1))   # PCM format
            f.write(struct.pack('<H', num_channels))
            f.write(struct.pack('<I', self.sample_rate))
            f.write(struct.pack('<I', self.sample_rate * num_channels * bytes_per_sample))
            f.write(struct.pack('<H', num_channels * bytes_per_sample))
            f.write(struct.pack('<H', 16))  # Bits per sample

            # Data chunk
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            f.write(audio_16bit.tobytes())
