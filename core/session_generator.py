"""
Automatic session generator for E-Stim 2B.

Generates dynamic sessions based on user-defined parameters such as:
- Preferred waveforms and frequencies
- Intensity curve (gentle start, build-up, climax, cool-down)
- Session duration and number of phases
- Variation and randomness levels
"""

import random
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from .waveforms import WaveformType
from .modulation import ModulationType, ModulationParams, EnvelopeADSR
from .patterns import PatternSegment, ChannelConfig, TransitionType
from .session import Session


class IntensityCurve(Enum):
    """Predefined intensity curves for session generation."""
    LINEAR_UP = "linear_up"           # Steady increase
    LINEAR_DOWN = "linear_down"       # Steady decrease
    TRIANGLE = "triangle"             # Up then down
    WAVE = "wave"                     # Multiple peaks
    PLATEAU = "plateau"               # Build up, sustain, release
    RANDOM = "random"                 # Randomized intensity
    ESCALATION = "escalation"         # Staircase up with breaks
    TEASE = "tease"                   # Build up, drop, repeat, climax


class SessionStyle(Enum):
    """Session style presets."""
    RELAXATION = "relaxation"         # Gentle, flowing
    RHYTHMIC = "rhythmic"             # Beat-based
    INTENSE = "intense"               # Strong, dynamic
    TEASING = "teasing"               # Variable, unpredictable
    MEDITATION = "meditation"         # Steady, monotone
    ADVENTURE = "adventure"           # Diverse patterns


# ── Style profiles: strict parameter constraints per session style ────
#
# Based on analysis of ~4000 real E-Stim audio files (Claude SSG, BigTip,
# EFun, Sparkie, Yoda, Stimaddict, Henk, etc.) the key characteristics
# of professional E-Stim signals are:
#
#   1. HIGH carrier frequencies: 200-1000 Hz (typically 300-800 Hz)
#      – this is what the E-Stim device converts to electrical pulses
#   2. Rich harmonic content: square/pulse/saw waveforms, not just sine
#   3. AM modulation at 0.5-10 Hz creates the "feel" pattern (throbbing,
#      pulsing, rhythmic sensations)
#   4. Significant stereo independence: L/R channels often have
#      different amplitudes, modulation depth, or slight frequency offsets
#   5. Slow frequency evolution: carrier drifts gradually over 30-200s
#   6. Pulse/burst patterns: variable duty cycles for texture variety
#
_STYLE_PROFILES = {
    SessionStyle.RELAXATION: {
        # Smooth carrier, moderate frequency, slow gentle AM
        'waveforms': [WaveformType.SINE, WaveformType.TRIANGLE, WaveformType.PULSE],
        'freq_range': (200.0, 500.0),
        'preferred_frequencies': [250, 300, 350, 400],
        'modulations': [ModulationType.TREMOLO, ModulationType.WAVE, ModulationType.AM],
        'mod_rate_range': (0.3, 2.0),
        'mod_depth_range': (0.3, 0.6),
        'modulation_probability': 0.85,
        'transition_duration_range': (3.0, 6.0),
        'max_freq_drift': 0.08,
        'waveform_change_prob': 0.10,
        'channel_symmetry_bias': 0.6,      # moderate L/R independence
        'duty_cycle_range': (0.3, 0.7),
        'stereo_freq_offset': (0.0, 15.0), # slight L/R detuning
    },
    SessionStyle.RHYTHMIC: {
        # Pulse/square carrier, rhythmic AM creating beat patterns
        'waveforms': [WaveformType.SQUARE, WaveformType.PULSE, WaveformType.SINE],
        'freq_range': (300.0, 700.0),
        'preferred_frequencies': [350, 440, 500, 600],
        'modulations': [ModulationType.AM, ModulationType.TREMOLO, ModulationType.WAVE],
        'mod_rate_range': (1.0, 6.0),
        'mod_depth_range': (0.4, 0.8),
        'modulation_probability': 0.90,
        'transition_duration_range': (2.0, 4.0),
        'max_freq_drift': 0.12,
        'waveform_change_prob': 0.25,
        'channel_symmetry_bias': 0.4,
        'duty_cycle_range': (0.2, 0.6),
        'stereo_freq_offset': (0.0, 30.0),
    },
    SessionStyle.INTENSE: {
        # Harsh carrier (square/saw/pulse), high freq, strong fast AM
        'waveforms': [WaveformType.SQUARE, WaveformType.SAWTOOTH, WaveformType.PULSE],
        'freq_range': (400.0, 900.0),
        'preferred_frequencies': [480, 560, 640, 800],
        'modulations': [ModulationType.AM, ModulationType.TREMOLO, ModulationType.FM],
        'mod_rate_range': (2.0, 10.0),
        'mod_depth_range': (0.5, 0.9),
        'modulation_probability': 0.95,
        'transition_duration_range': (1.5, 3.0),
        'max_freq_drift': 0.15,
        'waveform_change_prob': 0.30,
        'channel_symmetry_bias': 0.3,
        'duty_cycle_range': (0.15, 0.5),
        'stereo_freq_offset': (5.0, 50.0),
    },
    SessionStyle.TEASING: {
        # Variable carrier, unpredictable AM, high stereo independence
        'waveforms': [WaveformType.SINE, WaveformType.PULSE, WaveformType.SQUARE,
                      WaveformType.TRIANGLE],
        'freq_range': (250.0, 700.0),
        'preferred_frequencies': [300, 400, 500, 600],
        'modulations': [ModulationType.WAVE, ModulationType.TREMOLO,
                        ModulationType.RAMP_UP, ModulationType.RAMP_DOWN, ModulationType.AM],
        'mod_rate_range': (0.5, 5.0),
        'mod_depth_range': (0.3, 0.8),
        'modulation_probability': 0.85,
        'transition_duration_range': (2.0, 4.0),
        'max_freq_drift': 0.15,
        'waveform_change_prob': 0.30,
        'channel_symmetry_bias': 0.3,
        'duty_cycle_range': (0.2, 0.7),
        'stereo_freq_offset': (0.0, 40.0),
    },
    SessionStyle.MEDITATION: {
        # Smooth sine carrier, low-moderate freq, very slow AM
        'waveforms': [WaveformType.SINE, WaveformType.TRIANGLE],
        'freq_range': (200.0, 400.0),
        'preferred_frequencies': [250, 300, 350],
        'modulations': [ModulationType.WAVE, ModulationType.TREMOLO],
        'mod_rate_range': (0.2, 1.0),
        'mod_depth_range': (0.2, 0.5),
        'modulation_probability': 0.80,
        'transition_duration_range': (4.0, 8.0),
        'max_freq_drift': 0.05,
        'waveform_change_prob': 0.08,
        'channel_symmetry_bias': 0.7,
        'duty_cycle_range': (0.4, 0.7),
        'stereo_freq_offset': (0.0, 5.0),
    },
    SessionStyle.ADVENTURE: {
        # Full range of carriers and modulations, high variety
        'waveforms': [WaveformType.SINE, WaveformType.SQUARE, WaveformType.TRIANGLE,
                      WaveformType.SAWTOOTH, WaveformType.PULSE, WaveformType.BURST],
        'freq_range': (200.0, 900.0),
        'preferred_frequencies': [300, 440, 500, 640, 800],
        'modulations': [ModulationType.AM, ModulationType.FM,
                        ModulationType.TREMOLO, ModulationType.WAVE,
                        ModulationType.RAMP_UP, ModulationType.RAMP_DOWN],
        'mod_rate_range': (0.5, 8.0),
        'mod_depth_range': (0.3, 0.8),
        'modulation_probability': 0.90,
        'transition_duration_range': (1.5, 4.0),
        'max_freq_drift': 0.20,
        'waveform_change_prob': 0.35,
        'channel_symmetry_bias': 0.35,
        'duty_cycle_range': (0.15, 0.7),
        'stereo_freq_offset': (0.0, 60.0),
    },
}


@dataclass
class GeneratorConfig:
    """Configuration for the automatic session generator."""

    # General
    session_name: str = "Generierte Session"
    total_duration: float = 300.0     # Total session duration in seconds (5 min default)
    num_phases: int = 0               # Number of phases (0 = auto based on duration)

    # Style and curve
    style: SessionStyle = SessionStyle.RHYTHMIC
    intensity_curve: IntensityCurve = IntensityCurve.PLATEAU

    # Intensity range
    min_intensity: float = 0.2        # Minimum amplitude [0.0, 1.0]
    max_intensity: float = 0.9        # Maximum amplitude [0.0, 1.0]

    # Frequency preferences (carrier frequency for E-Stim)
    preferred_frequencies: List[float] = field(default_factory=lambda: [300, 400, 500, 600, 800])
    freq_range: Tuple[float, float] = (200.0, 800.0)

    # Waveform preferences
    allowed_waveforms: List[WaveformType] = field(default_factory=lambda: [
        WaveformType.SINE, WaveformType.SQUARE, WaveformType.TRIANGLE,
        WaveformType.SAWTOOTH, WaveformType.PULSE
    ])

    # Modulation preferences
    allowed_modulations: List[ModulationType] = field(default_factory=lambda: [
        ModulationType.AM, ModulationType.TREMOLO, ModulationType.WAVE
    ])
    modulation_probability: float = 0.85  # E-Stim signals almost always have AM

    # Variation
    randomness: float = 0.3           # Overall randomness [0.0, 1.0]
    channel_symmetry: float = 0.4     # How similar A and B should be [0.0=independent, 1.0=identical]

    # Transitions
    transition_duration: float = 2.0  # Default transition time
    preferred_transition: TransitionType = TransitionType.CROSSFADE

    # Envelope
    use_envelopes: bool = True
    envelope_probability: float = 0.4


class SessionGenerator:
    """
    Automatically generates E-Stim sessions based on configuration parameters.

    Creates varied, dynamic sessions that follow an intensity curve
    while respecting user preferences for waveforms, frequencies, and modulation.
    """

    def __init__(self, config: GeneratorConfig = None):
        self.config = config or GeneratorConfig()

    def generate(self, config: GeneratorConfig = None) -> Session:
        """
        Generate a complete session based on the configuration.

        Returns a Session object with all segments configured.
        """
        cfg = config or self.config

        session = Session(
            name=cfg.session_name,
            description=f"Auto-generiert | Stil: {cfg.style.value} | "
                       f"Kurve: {cfg.intensity_curve.value}",
        )

        # Determine number of phases
        num_phases = cfg.num_phases if cfg.num_phases > 0 else self._auto_num_phases(cfg)

        # Generate intensity curve
        intensities = self._generate_intensity_curve(cfg, num_phases)

        # Calculate segment durations
        durations = self._generate_durations(cfg, num_phases)

        # Generate each segment (pass previous for smooth transitions)
        prev_segment = None
        for i in range(num_phases):
            segment = self._generate_segment(
                cfg=cfg,
                index=i,
                total_phases=num_phases,
                intensity=intensities[i],
                duration=durations[i],
                prev_segment=prev_segment,
            )
            session.add_segment(segment)
            prev_segment = segment

        return session

    def _auto_num_phases(self, cfg: GeneratorConfig) -> int:
        """Determine optimal number of phases based on duration and style."""
        base_phase_duration = {
            SessionStyle.RELAXATION: 30.0,
            SessionStyle.RHYTHMIC: 20.0,
            SessionStyle.INTENSE: 15.0,
            SessionStyle.TEASING: 12.0,
            SessionStyle.MEDITATION: 45.0,
            SessionStyle.ADVENTURE: 18.0,
        }
        duration = base_phase_duration.get(cfg.style, 20.0)
        num = max(3, int(cfg.total_duration / duration))
        # For long sessions (>30min): vary segment length more to avoid monotony
        if cfg.total_duration > 1800:
            # Mix short and long segments — aim for 15-45s average
            num = max(num, int(cfg.total_duration / 25))
        return min(num, 500)  # Allow many phases for very long sessions

    def _generate_intensity_curve(self, cfg: GeneratorConfig, num_phases: int) -> List[float]:
        """Generate intensity values for each phase based on the selected curve."""
        t = np.linspace(0, 1, num_phases)

        curves = {
            IntensityCurve.LINEAR_UP: t,
            IntensityCurve.LINEAR_DOWN: 1.0 - t,
            IntensityCurve.TRIANGLE: 1.0 - np.abs(2.0 * t - 1.0),
            IntensityCurve.WAVE: 0.5 + 0.5 * np.sin(2 * np.pi * t * 2),
            IntensityCurve.PLATEAU: self._plateau_curve(t),
            IntensityCurve.RANDOM: np.random.uniform(0, 1, num_phases),
            IntensityCurve.ESCALATION: self._escalation_curve(t),
            IntensityCurve.TEASE: self._tease_curve(t),
        }

        raw = curves.get(cfg.intensity_curve, t)

        # Add randomness
        if cfg.randomness > 0:
            noise = np.random.uniform(-cfg.randomness * 0.3, cfg.randomness * 0.3, num_phases)
            raw = np.clip(raw + noise, 0, 1)

        # Scale to min/max intensity range
        intensities = cfg.min_intensity + raw * (cfg.max_intensity - cfg.min_intensity)
        return intensities.tolist()

    @staticmethod
    def _plateau_curve(t: np.ndarray) -> np.ndarray:
        """Build up → plateau → release intensity curve."""
        result = np.zeros_like(t)
        for i, v in enumerate(t):
            if v < 0.2:
                result[i] = v / 0.2
            elif v < 0.8:
                result[i] = 1.0
            else:
                result[i] = (1.0 - v) / 0.2
        return result

    @staticmethod
    def _escalation_curve(t: np.ndarray) -> np.ndarray:
        """Staircase escalation with small drops between steps."""
        steps = 5
        result = np.zeros_like(t)
        for i, v in enumerate(t):
            step = int(v * steps)
            within_step = (v * steps) % 1.0
            base = step / steps
            # Small rise within each step
            result[i] = base + (1.0 / steps) * within_step * 0.8
        return np.clip(result, 0, 1)

    @staticmethod
    def _tease_curve(t: np.ndarray) -> np.ndarray:
        """Tease curve: build up, sudden drop, repeat, final climax."""
        result = np.zeros_like(t)
        for i, v in enumerate(t):
            if v < 0.3:
                # Build up
                result[i] = v / 0.3 * 0.7
            elif v < 0.35:
                # Drop
                result[i] = 0.2
            elif v < 0.6:
                # Build up again
                result[i] = 0.2 + (v - 0.35) / 0.25 * 0.8
            elif v < 0.65:
                # Drop again
                result[i] = 0.3
            elif v < 0.9:
                # Final build
                result[i] = 0.3 + (v - 0.65) / 0.25 * 0.7
            else:
                # Peak and release
                result[i] = 1.0 - (v - 0.9) / 0.1 * 0.5
        return result

    def _generate_durations(self, cfg: GeneratorConfig, num_phases: int) -> List[float]:
        """Generate segment durations that sum to total_duration."""
        if num_phases == 0:
            return []

        # Base equal distribution
        base_duration = cfg.total_duration / num_phases

        # Add variation based on randomness
        durations = []
        for i in range(num_phases):
            variation = 1.0 + random.uniform(-cfg.randomness * 0.5, cfg.randomness * 0.5)
            d = base_duration * variation
            # For longer sessions: allow wider duration range (5s–90s) for variety
            if cfg.total_duration > 600:
                # Occasionally produce short bursts or long sustained segments
                if random.random() < 0.15:
                    d = random.uniform(3.0, 8.0)  # short burst
                elif random.random() < 0.10:
                    d = random.uniform(45.0, 90.0)  # sustained
            durations.append(d)

        # Normalize to match total duration
        total = sum(durations)
        scale = cfg.total_duration / total
        durations = [d * scale for d in durations]

        # Ensure minimum segment duration of 3 seconds
        durations = [max(3.0, d) for d in durations]

        return durations

    def _get_profile(self, cfg: GeneratorConfig) -> dict:
        """Get the style profile for the current session style."""
        return _STYLE_PROFILES.get(cfg.style, _STYLE_PROFILES[SessionStyle.RHYTHMIC])

    def _generate_segment(
        self,
        cfg: GeneratorConfig,
        index: int,
        total_phases: int,
        intensity: float,
        duration: float,
        prev_segment: Optional[PatternSegment] = None,
    ) -> PatternSegment:
        """Generate a single segment modelled on real E-Stim audio patterns.

        Architecture (based on analysis of ~4000 professional E-Stim files):

          Signal = Carrier(200-1000 Hz, rich waveform)
                 × AM_Envelope(0.5-10 Hz, depth 0.3-0.9)
                 × IntensityScale

        Left and right channels have independent but correlated
        parameters (frequency offsets, amplitude differences, different
        AM depths) to create spatial/travelling sensations.
        """
        profile = self._get_profile(cfg)
        sym_bias = profile.get('channel_symmetry_bias', cfg.channel_symmetry)
        # Effective symmetry: blend config slider with style recommendation
        eff_symmetry = cfg.channel_symmetry * 0.5 + sym_bias * 0.5

        # ── Carrier waveform (style-strict, prefer stability) ──
        waveform_a = self._select_waveform(profile, prev_segment, 'a')
        if random.random() < eff_symmetry:
            waveform_b = waveform_a
        else:
            waveform_b = self._select_waveform(profile, prev_segment, 'b')

        # ── Carrier frequency (gradual drift, high range) ──
        freq_a = self._select_frequency(profile, intensity, prev_segment, 'a', cfg.randomness)

        # Channel B: same carrier with optional stereo offset
        stereo_lo, stereo_hi = profile.get('stereo_freq_offset', (0.0, 20.0))
        if random.random() < eff_symmetry:
            # Slight detuning for spatial effect (like real E-Stim files)
            offset = random.uniform(stereo_lo, stereo_hi)
            if random.random() < 0.5:
                offset = -offset
            lo, hi = profile['freq_range']
            freq_b = float(np.clip(freq_a + offset, lo, hi))
        else:
            freq_b = self._select_frequency(profile, intensity, prev_segment, 'b', cfg.randomness)

        # ── Modulation: AM envelope is the core of E-Stim sensation ──
        mod_a = self._select_modulation(profile, intensity, prev_segment, 'a')

        # Channel B modulation: correlated but independent
        if random.random() < eff_symmetry * 0.7:
            # Similar modulation with slight rate/depth variation
            rate_lo, rate_hi = profile['mod_rate_range']
            depth_lo, depth_hi = profile['mod_depth_range']
            mod_b = ModulationParams(
                mod_type=mod_a.mod_type,
                rate=float(np.clip(
                    mod_a.rate * random.uniform(0.8, 1.2), rate_lo, rate_hi)),
                depth=float(np.clip(
                    mod_a.depth * random.uniform(0.7, 1.3), depth_lo, depth_hi)),
            )
        else:
            mod_b = self._select_modulation(profile, intensity, prev_segment, 'b')

        # ── Duty cycle: controls pulse width for PULSE/BURST waveforms ──
        dc_lo, dc_hi = profile.get('duty_cycle_range', (0.2, 0.7))
        duty_a = random.uniform(dc_lo, dc_hi)
        if random.random() < eff_symmetry:
            duty_b = duty_a * random.uniform(0.9, 1.1)
            duty_b = float(np.clip(duty_b, dc_lo, dc_hi))
        else:
            duty_b = random.uniform(dc_lo, dc_hi)

        # ── Amplitude: L/R independence for spatial effect ──
        amp_a = intensity
        if random.random() < eff_symmetry:
            amp_b = intensity * random.uniform(0.85, 1.0)
        else:
            # Significant L/R amplitude difference (like BT / Heaven and Hell)
            amp_b = intensity * random.uniform(0.5, 1.0)

        # ── Envelope ──
        use_envelope = cfg.use_envelopes and random.random() < cfg.envelope_probability
        envelope = (self._generate_envelope(cfg, duration, intensity)
                    if use_envelope else EnvelopeADSR())

        # ── Transition ──
        is_last = index == total_phases - 1
        td_lo, td_hi = profile['transition_duration_range']
        transition_dur = random.uniform(td_lo, td_hi)
        transition = TransitionType.FADE_OUT_IN if is_last else TransitionType.CROSSFADE

        # Phase name
        phase_name = self._get_phase_name(index, total_phases, cfg.style)

        segment = PatternSegment(
            name=phase_name,
            duration=duration,
            channel_a=ChannelConfig(
                waveform=waveform_a,
                frequency=freq_a,
                amplitude=amp_a,
                duty_cycle=duty_a,
            ),
            channel_b=ChannelConfig(
                waveform=waveform_b,
                frequency=freq_b,
                amplitude=amp_b,
                duty_cycle=duty_b,
            ),
            modulation_a=mod_a,
            modulation_b=mod_b,
            use_envelope=use_envelope,
            envelope=envelope,
            transition=transition,
            transition_duration=min(transition_dur, duration * 0.3),
        )

        return segment

    # ── Style-strict selection helpers ────────────────────────────────

    def _select_waveform(
        self, profile: dict, prev_segment: Optional[PatternSegment], channel: str,
    ) -> WaveformType:
        """Select a waveform strictly from the style profile.

        Prefers keeping the previous segment's waveform to avoid jarring
        changes.  The waveform_change_prob controls how often a switch
        happens.
        """
        allowed = profile['waveforms']
        if not allowed:
            return WaveformType.SINE

        if prev_segment is not None:
            prev_wf = (prev_segment.channel_a.waveform if channel == 'a'
                       else prev_segment.channel_b.waveform)
            if prev_wf in allowed and random.random() > profile['waveform_change_prob']:
                return prev_wf

        return random.choice(allowed)

    def _select_frequency(
        self, profile: dict, intensity: float,
        prev_segment: Optional[PatternSegment], channel: str,
        randomness: float,
    ) -> float:
        """Select carrier frequency within the style's range, drifting gradually.

        Real E-Stim files show carriers at 200-1000 Hz with slow drift
        over time (e.g. Claude SSG-C.7 Dynamique rises 600→700 Hz over 200s).
        """
        lo, hi = profile['freq_range']

        if prev_segment is not None:
            prev_freq = (prev_segment.channel_a.frequency if channel == 'a'
                         else prev_segment.channel_b.frequency)
            max_drift = profile['max_freq_drift']
            drift = random.uniform(-max_drift, max_drift)
            freq = prev_freq * (1.0 + drift)
        else:
            preferred = profile['preferred_frequencies']
            if preferred and random.random() > randomness:
                freq = random.choice(preferred)
            else:
                freq = random.uniform(lo, hi)

        return float(np.clip(freq, lo, hi))

    def _select_modulation(
        self, profile: dict, intensity: float,
        prev_segment: Optional[PatternSegment], channel: str,
    ) -> ModulationParams:
        """Select AM modulation — the core of E-Stim sensation patterns.

        Real E-Stim files use AM at 0.5-10 Hz with depth 0.3-0.9.
        This creates the pulsing/throbbing/rhythmic feel.
        Modulation is almost always present in professional E-Stim audio.
        """
        if random.random() > profile['modulation_probability']:
            return ModulationParams(mod_type=ModulationType.NONE)

        allowed = [m for m in profile['modulations'] if m != ModulationType.NONE]
        if not allowed:
            return ModulationParams(mod_type=ModulationType.NONE)

        rate_lo, rate_hi = profile['mod_rate_range']
        depth_lo, depth_hi = profile['mod_depth_range']

        # Prefer previous modulation type for smooth transitions
        if prev_segment is not None:
            prev_mod = (prev_segment.modulation_a if channel == 'a'
                        else prev_segment.modulation_b)
            if prev_mod.mod_type in allowed and random.random() > 0.3:
                new_rate = prev_mod.rate * random.uniform(0.85, 1.15)
                new_depth = prev_mod.depth * random.uniform(0.85, 1.15)
                return ModulationParams(
                    mod_type=prev_mod.mod_type,
                    rate=float(np.clip(new_rate, rate_lo, rate_hi)),
                    depth=float(np.clip(new_depth, depth_lo, depth_hi)),
                )

        mod_type = random.choice(allowed)
        rate = random.uniform(rate_lo, rate_hi)
        # Higher intensity → deeper modulation for more pronounced effect
        depth = random.uniform(depth_lo, depth_hi) * (0.6 + 0.4 * intensity)
        depth = float(np.clip(depth, depth_lo, depth_hi))

        return ModulationParams(mod_type=mod_type, rate=rate, depth=depth)

    def _generate_envelope(self, cfg: GeneratorConfig, duration: float, intensity: float) -> EnvelopeADSR:
        """Generate an ADSR envelope for a segment."""
        attack = random.uniform(0.05, min(0.5, duration * 0.15))
        decay = random.uniform(0.05, min(0.3, duration * 0.1))
        sustain = 0.5 + 0.4 * intensity
        release = random.uniform(0.1, min(0.5, duration * 0.15))
        return EnvelopeADSR(attack=attack, decay=decay, sustain=sustain, release=release)

    def _get_phase_name(self, index: int, total: int, style: SessionStyle) -> str:
        """Generate a descriptive name for a phase."""
        progress = index / max(total - 1, 1)

        phase_names = {
            SessionStyle.RELAXATION: [
                "Einstimmung", "Sanfter Beginn", "Wärme", "Tiefe Entspannung",
                "Fließende Wellen", "Sanftes Gleiten", "Innere Ruhe",
                "Schweben", "Geborgenheit", "Ausklang",
            ],
            SessionStyle.INTENSE: [
                "Aufwärmen", "Erste Stufe", "Zündung", "Steigerung",
                "Volle Kraft", "Druck", "Höhepunkt", "Nachbeben",
                "Letzte Welle", "Abkühlung",
            ],
            SessionStyle.TEASING: [
                "Annäherung", "Aufbau", "Steigerung", "Rückzug", "Spannung",
                "Erneuter Aufbau", "Überraschung", "Höhepunkt",
                "Nachlassen", "Finale",
            ],
            SessionStyle.MEDITATION: [
                "Zentrierung", "Stille Kraft", "Tiefe", "Gleichmäßig",
                "Erdung", "Fokus", "Weite", "Präsenz",
                "Harmonie", "Auflösung",
            ],
            SessionStyle.ADVENTURE: [
                "Aufbruch", "Erkundung", "Entdeckung", "Strom",
                "Abenteuer", "Wendepunkt", "Neues Terrain",
                "Wildnis", "Gipfel", "Heimkehr",
            ],
            SessionStyle.RHYTHMIC: [
                "Takt", "Groove", "Beat", "Flow", "Puls",
                "Rhythmus", "Trommel", "Synkope", "Crescendo", "Finale",
            ],
        }

        names = phase_names.get(style, [f"Phase {i}" for i in range(1, 11)])

        # Cycle through names for sessions with many segments
        name_idx = int(progress * (len(names) - 1))
        base_name = names[min(name_idx, len(names) - 1)]

        return f"{base_name} ({index + 1}/{total})"


def quick_generate(
    duration_minutes: float = 5.0,
    style: str = "rhythmic",
    intensity: str = "medium",
    curve: str = "plateau",
) -> Session:
    """
    Quick session generation with simple parameters.

    Args:
        duration_minutes: Session duration in minutes
        style: One of: relaxation, rhythmic, intense, teasing, meditation, adventure
        intensity: One of: low, medium, high
        curve: One of: linear_up, linear_down, triangle, wave, plateau, random, escalation, tease

    Returns:
        Generated Session object
    """
    intensity_map = {
        "low": (0.1, 0.5),
        "medium": (0.2, 0.7),
        "high": (0.4, 0.95),
    }
    min_int, max_int = intensity_map.get(intensity, (0.2, 0.7))

    config = GeneratorConfig(
        session_name=f"Auto: {style.capitalize()} ({duration_minutes:.0f} Min)",
        total_duration=duration_minutes * 60,
        style=SessionStyle(style),
        intensity_curve=IntensityCurve(curve),
        min_intensity=min_int,
        max_intensity=max_int,
        freq_range=(200.0, 800.0),
    )

    generator = SessionGenerator(config)
    return generator.generate()
