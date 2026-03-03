"""
Real-time audio engine for E-Stim 2B.

Handles real-time audio generation and playback with support for:
- Thread-safe parameter updates during playback
- Session playback with segment transitions
- Live modification of all parameters
- WAV file export
"""

import threading
import time
import numpy as np
from enum import Enum
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field

from .android_audio import create_audio_stream, is_android

try:
    import sounddevice as sd
    HAS_AUDIO = True
except ImportError:
    # On Android, sounddevice won't be available but AudioTrack will
    HAS_AUDIO = is_android()

from .waveforms import WaveformType, StereoWaveformGenerator
from .modulation import Modulator, ModulationParams, ModulationType, EnvelopeADSR
from .patterns import PatternSegment, ChannelConfig, TransitionType
from .session import Session


class EngineState(Enum):
    """Audio engine states."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass
class LiveParams:
    """
    Thread-safe live parameters that can be modified during playback.
    All changes take effect in the next audio buffer cycle.
    """
    # Channel A
    waveform_a: WaveformType = WaveformType.SINE
    frequency_a: float = 80.0
    amplitude_a: float = 0.7
    duty_cycle_a: float = 0.5

    # Channel B
    waveform_b: WaveformType = WaveformType.SINE
    frequency_b: float = 80.0
    amplitude_b: float = 0.7
    duty_cycle_b: float = 0.5

    # Modulation A
    mod_type_a: ModulationType = ModulationType.NONE
    mod_rate_a: float = 1.0
    mod_depth_a: float = 0.5

    # Modulation B
    mod_type_b: ModulationType = ModulationType.NONE
    mod_rate_b: float = 1.0
    mod_depth_b: float = 0.5

    # Master controls
    master_volume: float = 0.8
    balance: float = 0.0  # -1.0 = full left/A, 0.0 = center, 1.0 = full right/B

    # Lock for thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, **kwargs):
        """Thread-safe parameter update."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key) and not key.startswith('_'):
                    setattr(self, key, value)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of all parameters.

        Individual attribute reads are atomic in CPython (GIL) so we
        can avoid locking here – this is the hot path called from the
        audio-callback thread and must never block.
        """
        return {
            'waveform_a': self.waveform_a,
            'frequency_a': self.frequency_a,
            'amplitude_a': self.amplitude_a,
            'duty_cycle_a': self.duty_cycle_a,
            'waveform_b': self.waveform_b,
            'frequency_b': self.frequency_b,
            'amplitude_b': self.amplitude_b,
            'duty_cycle_b': self.duty_cycle_b,
            'mod_type_a': self.mod_type_a,
            'mod_rate_a': self.mod_rate_a,
            'mod_depth_a': self.mod_depth_a,
            'mod_type_b': self.mod_type_b,
            'mod_rate_b': self.mod_rate_b,
            'mod_depth_b': self.mod_depth_b,
            'master_volume': self.master_volume,
            'balance': self.balance,
        }

    def load_from_segment(self, segment: PatternSegment):
        """Load parameters from a pattern segment."""
        self.update(
            waveform_a=segment.channel_a.waveform,
            frequency_a=segment.channel_a.frequency,
            amplitude_a=segment.channel_a.amplitude,
            duty_cycle_a=segment.channel_a.duty_cycle,
            waveform_b=segment.channel_b.waveform,
            frequency_b=segment.channel_b.frequency,
            amplitude_b=segment.channel_b.amplitude,
            duty_cycle_b=segment.channel_b.duty_cycle,
            mod_type_a=segment.modulation_a.mod_type,
            mod_rate_a=segment.modulation_a.rate,
            mod_depth_a=segment.modulation_a.depth,
            mod_type_b=segment.modulation_b.mod_type,
            mod_rate_b=segment.modulation_b.rate,
            mod_depth_b=segment.modulation_b.depth,
        )


class AudioEngine:
    """
    Real-time audio engine for E-Stim 2B signal generation and playback.

    Supports:
    - Free-play mode: Generate audio based on live parameters
    - Session mode: Play back a complete session with segments and transitions
    - Live parameter modification during playback
    - Callback hooks for UI updates

    Uses a short crossfade to eliminate clicks when parameters change.
    """

    # Audio buffer settings
    BUFFER_SIZE = 2048   # Samples per buffer (~46 ms at 44100 – more stable)
    SAMPLE_RATE = 44100
    CROSSFADE_SAMPLES = 64  # ~1.5 ms crossfade to eliminate clicks

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 2048):
        self.sample_rate = sample_rate
        self.BUFFER_SIZE = buffer_size

        # Audio generators
        self.generator = StereoWaveformGenerator(sample_rate)
        self.modulator_a = Modulator(sample_rate)
        self.modulator_b = Modulator(sample_rate)

        # State
        self.state = EngineState.STOPPED
        self.live_params = LiveParams()

        # Crossfade: keep the tail of the previous buffer
        self._prev_tail: Optional[np.ndarray] = None

        # Pre-compute crossfade curves (avoids allocation in callback)
        cf = self.CROSSFADE_SAMPLES
        self._fade_in = np.linspace(0.0, 1.0, cf, dtype=np.float32).reshape(-1, 1)
        self._fade_out = 1.0 - self._fade_in

        # Re-usable modulation param objects (avoid per-buffer allocation)
        self._mod_params_a: Optional[ModulationParams] = None
        self._mod_params_b: Optional[ModulationParams] = None

        # Session playback
        self._session: Optional[Session] = None
        self._session_position = 0.0  # Current playback position in seconds
        self._current_segment_idx = 0
        self._session_start_time = 0.0

        # Stream
        self._stream = None

        # Callbacks
        self._on_position_update: Optional[Callable[[float, int], None]] = None
        self._on_state_change: Optional[Callable[[EngineState], None]] = None
        self._on_segment_change: Optional[Callable[[int, PatternSegment], None]] = None

        # Throttle position-update callback (called from audio thread)
        self._position_cb_counter = 0
        self._POSITION_CB_EVERY = 5  # only notify every N buffers (~230 ms at 2048/44100)

        # Threading
        self._lock = threading.Lock()

    def set_callbacks(
        self,
        on_position_update: Callable[[float, int], None] = None,
        on_state_change: Callable[[EngineState], None] = None,
        on_segment_change: Callable[[int, PatternSegment], None] = None,
    ):
        """Set callback functions for UI updates."""
        self._on_position_update = on_position_update
        self._on_state_change = on_state_change
        self._on_segment_change = on_segment_change

    def _set_state(self, state: EngineState):
        """Update state and notify callback."""
        self.state = state
        if self._on_state_change:
            self._on_state_change(state)

    # ─── Free Play Mode ─────────────────────────────────────────────

    def play_free(self):
        """Start free-play mode with live parameters."""
        if not HAS_AUDIO:
            raise RuntimeError("Kein Audio-Backend verfügbar. Installiere sounddevice: pip install sounddevice")

        if self.state == EngineState.PLAYING:
            return

        self._session = None
        self._prev_tail = None
        self.generator.reset_phase()
        self.modulator_a.reset_phase()
        self.modulator_b.reset_phase()

        self._start_stream()
        self._set_state(EngineState.PLAYING)

    # ─── Session Playback ────────────────────────────────────────────

    def play_session(self, session: Session):
        """Start playing a session."""
        if not HAS_AUDIO:
            raise RuntimeError("Kein Audio-Backend verfügbar. Installiere sounddevice: pip install sounddevice")

        self.stop()

        self._session = session
        self._session_position = 0.0
        self._current_segment_idx = 0
        self._prev_tail = None
        self.live_params.master_volume = session.master_volume

        if session.segments:
            self.live_params.load_from_segment(session.segments[0])
            if self._on_segment_change:
                self._on_segment_change(0, session.segments[0])

        self.generator.reset_phase()
        self.modulator_a.reset_phase()
        self.modulator_b.reset_phase()

        self._start_stream()
        self._session_start_time = time.time()
        self._set_state(EngineState.PLAYING)

    def seek(self, position: float):
        """Seek to a position in the session (in seconds)."""
        if self._session is None:
            return

        with self._lock:
            self._session_position = max(0, min(position, self._session.total_duration))
            # Find the correct segment
            elapsed = 0.0
            for i, seg in enumerate(self._session.segments):
                if elapsed + seg.duration > self._session_position:
                    if i != self._current_segment_idx:
                        self._current_segment_idx = i
                        self.live_params.load_from_segment(seg)
                        if self._on_segment_change:
                            self._on_segment_change(i, seg)
                    break
                elapsed += seg.duration

    # ─── Common Controls ────────────────────────────────────────────

    def pause(self):
        """Pause playback."""
        if self.state == EngineState.PLAYING:
            if self._stream:
                self._stream.stop()
            self._set_state(EngineState.PAUSED)

    def resume(self):
        """Resume playback."""
        if self.state == EngineState.PAUSED:
            if self._stream:
                self._stream.start()
            self._set_state(EngineState.PLAYING)

    def stop(self):
        """Stop playback completely."""
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        self._session_position = 0.0
        self._current_segment_idx = 0
        self._prev_tail = None
        self._set_state(EngineState.STOPPED)

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.state == EngineState.PLAYING:
            self.pause()
        elif self.state == EngineState.PAUSED:
            self.resume()

    # ─── Live Parameter Modification ────────────────────────────────

    def set_frequency(self, channel: str, frequency: float):
        """Set frequency for a channel ('a' or 'b')."""
        if channel.lower() == 'a':
            self.live_params.update(frequency_a=frequency)
        else:
            self.live_params.update(frequency_b=frequency)

    def set_amplitude(self, channel: str, amplitude: float):
        """Set amplitude for a channel."""
        amplitude = max(0.0, min(1.0, amplitude))
        if channel.lower() == 'a':
            self.live_params.update(amplitude_a=amplitude)
        else:
            self.live_params.update(amplitude_b=amplitude)

    def set_waveform(self, channel: str, waveform: WaveformType):
        """Set waveform type for a channel."""
        if channel.lower() == 'a':
            self.live_params.update(waveform_a=waveform)
        else:
            self.live_params.update(waveform_b=waveform)

    def set_modulation(self, channel: str, mod_type: ModulationType, rate: float = None, depth: float = None):
        """Set modulation for a channel."""
        if channel.lower() == 'a':
            updates = {'mod_type_a': mod_type}
            if rate is not None:
                updates['mod_rate_a'] = rate
            if depth is not None:
                updates['mod_depth_a'] = depth
            self.live_params.update(**updates)
        else:
            updates = {'mod_type_b': mod_type}
            if rate is not None:
                updates['mod_rate_b'] = rate
            if depth is not None:
                updates['mod_depth_b'] = depth
            self.live_params.update(**updates)

    def set_master_volume(self, volume: float):
        """Set master volume [0.0, 1.0]."""
        self.live_params.update(master_volume=max(0.0, min(1.0, volume)))

    def set_balance(self, balance: float):
        """Set channel balance [-1.0 = A only, 0.0 = center, 1.0 = B only]."""
        self.live_params.update(balance=max(-1.0, min(1.0, balance)))

    # ─── Audio Stream ────────────────────────────────────────────────

    def _start_stream(self):
        """Initialize and start the audio output stream."""
        if self._stream:
            try:
                self._stream.close()
            except Exception:
                pass

        # Use platform-abstracted audio stream (sounddevice on Desktop, AudioTrack on Android)
        self._stream = create_audio_stream(
            samplerate=self.sample_rate,
            channels=2,
            blocksize=self.BUFFER_SIZE,
            dtype='float32',
            callback=self._audio_callback,
        )
        self._stream.start()

    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Audio callback - called by sounddevice for each buffer of audio data.
        This runs in a separate thread and must be fast.

        A short crossfade is applied at the start of each buffer against
        the tail of the previous buffer to eliminate clicks caused by
        waveform-type or parameter changes.
        """
        try:
            # Get current parameters (lock-free – see LiveParams.get_snapshot)
            params = self.live_params.get_snapshot()

            # Handle session segment tracking
            if self._session:
                self._update_session_position(frames)

            # Generate stereo signal directly into float32 to avoid
            # a costly dtype conversion at the end.
            stereo = self.generator.generate_stereo_block(
                num_samples=frames,
                waveform_a=params['waveform_a'],
                frequency_a=params['frequency_a'],
                amplitude_a=params['amplitude_a'],
                duty_cycle_a=params['duty_cycle_a'],
                waveform_b=params['waveform_b'],
                frequency_b=params['frequency_b'],
                amplitude_b=params['amplitude_b'],
                duty_cycle_b=params['duty_cycle_b'],
            )

            # Re-use cached ModulationParams to avoid allocation per buffer
            # Apply modulation to Channel A
            if params['mod_type_a'] != ModulationType.NONE:
                if self._mod_params_a is None:
                    self._mod_params_a = ModulationParams()
                self._mod_params_a.mod_type = params['mod_type_a']
                self._mod_params_a.rate = params['mod_rate_a']
                self._mod_params_a.depth = params['mod_depth_a']
                stereo[:, 0] = self.modulator_a.apply(stereo[:, 0], self._mod_params_a, continuous=True)

            # Apply modulation to Channel B
            if params['mod_type_b'] != ModulationType.NONE:
                if self._mod_params_b is None:
                    self._mod_params_b = ModulationParams()
                self._mod_params_b.mod_type = params['mod_type_b']
                self._mod_params_b.rate = params['mod_rate_b']
                self._mod_params_b.depth = params['mod_depth_b']
                stereo[:, 1] = self.modulator_b.apply(stereo[:, 1], self._mod_params_b, continuous=True)

            # Apply balance (in-place)
            balance = params['balance']
            if balance != 0.0:
                if balance < 0:
                    stereo[:, 1] *= (1.0 + balance)
                else:
                    stereo[:, 0] *= (1.0 - balance)

            # Apply master volume (in-place)
            stereo *= params['master_volume']

            # ── Crossfade with previous buffer tail ───────────
            cf = min(self.CROSSFADE_SAMPLES, frames)
            if self._prev_tail is not None and cf > 0:
                # Re-use pre-computed fade curves
                stereo[:cf] = stereo[:cf] * self._fade_in[:cf] + self._prev_tail[-cf:] * self._fade_out[:cf]

            # Save tail for next crossfade
            self._prev_tail = stereo[-cf:].copy() if cf > 0 else None

            # Clip to safe range and write (in-place)
            np.clip(stereo, -1.0, 1.0, out=stereo)

            outdata[:] = stereo.astype(np.float32)

        except Exception as e:
            # On error, output silence
            outdata[:] = 0
            self._prev_tail = None
            print(f"Audio callback Fehler: {e}")

    def _update_session_position(self, frames: int):
        """Update session position and handle segment transitions."""
        if not self._session or not self._session.segments:
            return

        # Advance position
        self._session_position += frames / self.sample_rate

        # Check if we've passed the end of the session
        total = self._session.total_duration
        if self._session_position >= total:
            if self._session.loop:
                self._session_position = 0.0
                self._current_segment_idx = 0
                self.live_params.load_from_segment(self._session.segments[0])
            else:
                # Session finished
                self._session_position = total
                # Will trigger stop on next cycle
                return

        # Find current segment
        elapsed = 0.0
        for i, seg in enumerate(self._session.segments):
            if elapsed + seg.duration > self._session_position:
                if i != self._current_segment_idx:
                    self._current_segment_idx = i
                    self._apply_segment_transition(seg)
                    if self._on_segment_change:
                        self._on_segment_change(i, seg)
                break
            elapsed += seg.duration

        # Notify position update (throttled – skip most buffers)
        if self._on_position_update:
            self._position_cb_counter += 1
            if self._position_cb_counter >= self._POSITION_CB_EVERY:
                self._position_cb_counter = 0
                self._on_position_update(self._session_position, self._current_segment_idx)

    def _apply_segment_transition(self, new_segment: PatternSegment):
        """Apply transition effect when changing segments."""
        # For now, load segment parameters directly
        # TODO: Implement crossfade transitions between segments
        self.live_params.load_from_segment(new_segment)

    # ─── Properties ─────────────────────────────────────────────────

    @property
    def position(self) -> float:
        """Current playback position in seconds."""
        return self._session_position

    @property
    def current_segment(self) -> Optional[PatternSegment]:
        """Currently playing segment."""
        if self._session and self._session.segments:
            if self._current_segment_idx < len(self._session.segments):
                return self._session.segments[self._current_segment_idx]
        return None

    @property
    def is_playing(self) -> bool:
        return self.state == EngineState.PLAYING

    @property
    def is_paused(self) -> bool:
        return self.state == EngineState.PAUSED

    @property
    def is_stopped(self) -> bool:
        return self.state == EngineState.STOPPED
