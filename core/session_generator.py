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
# Each style strictly defines which waveforms, frequencies, modulations
# are allowed, plus drift limits for smooth segment-to-segment transitions.
_STYLE_PROFILES = {
    SessionStyle.RELAXATION: {
        'waveforms': [WaveformType.SINE, WaveformType.TRIANGLE],
        'freq_range': (20.0, 80.0),
        'preferred_frequencies': [30, 40, 50, 60, 80],
        'modulations': [ModulationType.NONE, ModulationType.TREMOLO, ModulationType.WAVE],
        'mod_rate_range': (0.1, 1.0),
        'mod_depth_range': (0.1, 0.4),
        'modulation_probability': 0.5,
        'transition_duration_range': (3.0, 5.0),
        'max_freq_drift': 0.15,
        'waveform_change_prob': 0.15,
    },
    SessionStyle.RHYTHMIC: {
        'waveforms': [WaveformType.SINE, WaveformType.SQUARE, WaveformType.PULSE],
        'freq_range': (40.0, 150.0),
        'preferred_frequencies': [50, 60, 80, 100, 120],
        'modulations': [ModulationType.NONE, ModulationType.AM, ModulationType.TREMOLO],
        'mod_rate_range': (0.5, 3.0),
        'mod_depth_range': (0.2, 0.6),
        'modulation_probability': 0.7,
        'transition_duration_range': (2.0, 3.5),
        'max_freq_drift': 0.25,
        'waveform_change_prob': 0.3,
    },
    SessionStyle.INTENSE: {
        'waveforms': [WaveformType.SQUARE, WaveformType.SAWTOOTH, WaveformType.PULSE],
        'freq_range': (60.0, 250.0),
        'preferred_frequencies': [80, 100, 120, 150, 200],
        'modulations': [ModulationType.NONE, ModulationType.AM, ModulationType.TREMOLO,
                        ModulationType.FM],
        'mod_rate_range': (1.0, 5.0),
        'mod_depth_range': (0.3, 0.8),
        'modulation_probability': 0.7,
        'transition_duration_range': (1.5, 2.5),
        'max_freq_drift': 0.30,
        'waveform_change_prob': 0.35,
    },
    SessionStyle.TEASING: {
        'waveforms': [WaveformType.SINE, WaveformType.PULSE, WaveformType.TRIANGLE],
        'freq_range': (30.0, 180.0),
        'preferred_frequencies': [40, 60, 80, 100, 150],
        'modulations': [ModulationType.NONE, ModulationType.WAVE, ModulationType.TREMOLO,
                        ModulationType.RAMP_UP, ModulationType.RAMP_DOWN],
        'mod_rate_range': (0.3, 2.5),
        'mod_depth_range': (0.2, 0.7),
        'modulation_probability': 0.6,
        'transition_duration_range': (2.5, 4.0),
        'max_freq_drift': 0.20,
        'waveform_change_prob': 0.25,
    },
    SessionStyle.MEDITATION: {
        'waveforms': [WaveformType.SINE, WaveformType.TRIANGLE],
        'freq_range': (20.0, 60.0),
        'preferred_frequencies': [30, 40, 50],
        'modulations': [ModulationType.NONE, ModulationType.WAVE],
        'mod_rate_range': (0.05, 0.5),
        'mod_depth_range': (0.1, 0.3),
        'modulation_probability': 0.4,
        'transition_duration_range': (4.0, 6.0),
        'max_freq_drift': 0.10,
        'waveform_change_prob': 0.10,
    },
    SessionStyle.ADVENTURE: {
        'waveforms': [WaveformType.SINE, WaveformType.SQUARE, WaveformType.TRIANGLE,
                      WaveformType.SAWTOOTH, WaveformType.PULSE],
        'freq_range': (20.0, 300.0),
        'preferred_frequencies': [40, 60, 80, 100, 150, 200],
        'modulations': [ModulationType.NONE, ModulationType.AM, ModulationType.FM,
                        ModulationType.TREMOLO, ModulationType.WAVE],
        'mod_rate_range': (0.3, 4.0),
        'mod_depth_range': (0.2, 0.7),
        'modulation_probability': 0.6,
        'transition_duration_range': (1.5, 3.0),
        'max_freq_drift': 0.35,
        'waveform_change_prob': 0.40,
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

    # Frequency preferences
    preferred_frequencies: List[float] = field(default_factory=lambda: [30, 60, 80, 100, 150])
    freq_range: Tuple[float, float] = (10.0, 250.0)

    # Waveform preferences
    allowed_waveforms: List[WaveformType] = field(default_factory=lambda: [
        WaveformType.SINE, WaveformType.SQUARE, WaveformType.TRIANGLE,
        WaveformType.SAWTOOTH, WaveformType.PULSE
    ])

    # Modulation preferences
    allowed_modulations: List[ModulationType] = field(default_factory=lambda: [
        ModulationType.NONE, ModulationType.AM, ModulationType.TREMOLO, ModulationType.WAVE
    ])
    modulation_probability: float = 0.6  # Chance of modulation per segment

    # Variation
    randomness: float = 0.3           # Overall randomness [0.0, 1.0]
    channel_symmetry: float = 0.7     # How similar A and B should be [0.0=independent, 1.0=identical]

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
        """Generate a single segment, smoothly drifting from the previous one.

        Uses the style profile to strictly limit waveforms, frequencies,
        and modulations.  When a previous segment exists, parameters
        drift gradually instead of jumping randomly.
        """
        profile = self._get_profile(cfg)

        # ── Waveform (style-strict, prefer stability) ──
        waveform_a = self._select_waveform(profile, prev_segment, 'a')
        waveform_b = self._select_waveform_b(cfg, profile, waveform_a, prev_segment)

        # ── Frequency (gradual drift from previous) ──
        freq_a = self._select_frequency(profile, intensity, prev_segment, 'a', cfg.randomness)
        freq_b = self._select_frequency_b(cfg, profile, freq_a, prev_segment)

        # ── Modulation (style-strict) ──
        mod_a = self._select_modulation(profile, intensity, prev_segment, 'a')
        mod_b = self._select_modulation_b(cfg, profile, mod_a, prev_segment)

        # ── Duty cycle ──
        duty_a = self._select_duty_cycle(cfg, intensity)
        duty_b = (duty_a if cfg.channel_symmetry > random.random()
                  else self._select_duty_cycle(cfg, intensity))

        # ── Envelope ──
        use_envelope = cfg.use_envelopes and random.random() < cfg.envelope_probability
        envelope = (self._generate_envelope(cfg, duration, intensity)
                    if use_envelope else EnvelopeADSR())

        # ── Transition (always crossfade between segments for smoothness) ──
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
                amplitude=intensity,
                duty_cycle=duty_a,
            ),
            channel_b=ChannelConfig(
                waveform=waveform_b,
                frequency=freq_b,
                amplitude=intensity * (0.9 + random.random() * 0.1
                                       if cfg.channel_symmetry < 1.0 else 1.0),
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

    def _select_waveform_b(
        self, cfg: GeneratorConfig, profile: dict,
        waveform_a: WaveformType, prev_segment: Optional[PatternSegment],
    ) -> WaveformType:
        """Select waveform B — prefers matching A for channel symmetry."""
        if random.random() < cfg.channel_symmetry:
            return waveform_a
        return self._select_waveform(profile, prev_segment, 'b')

    def _select_frequency(
        self, profile: dict, intensity: float,
        prev_segment: Optional[PatternSegment], channel: str,
        randomness: float,
    ) -> float:
        """Select frequency within the style's range, drifting gradually.

        If a previous segment exists the new frequency drifts at most
        max_freq_drift (e.g. 15 %) from the previous value, clamped to
        the style's allowed range.
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

    def _select_frequency_b(
        self, cfg: GeneratorConfig, profile: dict,
        freq_a: float, prev_segment: Optional[PatternSegment],
    ) -> float:
        """Select frequency B — similar to A with optional slight detuning."""
        lo, hi = profile['freq_range']
        if random.random() < cfg.channel_symmetry:
            detune = random.uniform(-3, 3)
            return float(np.clip(freq_a + detune, lo, hi))
        return self._select_frequency(profile, 0.5, prev_segment, 'b', 0.3)

    def _select_modulation(
        self, profile: dict, intensity: float,
        prev_segment: Optional[PatternSegment], channel: str,
    ) -> ModulationParams:
        """Select modulation strictly from the style profile.

        Prefers keeping the previous modulation type and drifts
        rate / depth gently for smooth transitions.
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
        depth = random.uniform(depth_lo, depth_hi) * (0.5 + 0.5 * intensity)

        return ModulationParams(mod_type=mod_type, rate=rate, depth=depth)

    def _select_modulation_b(
        self, cfg: GeneratorConfig, profile: dict,
        mod_a: ModulationParams, prev_segment: Optional[PatternSegment],
    ) -> ModulationParams:
        """Select modulation B — prefers matching A."""
        if random.random() < cfg.channel_symmetry:
            rate_lo, rate_hi = profile['mod_rate_range']
            depth_lo, depth_hi = profile['mod_depth_range']
            return ModulationParams(
                mod_type=mod_a.mod_type,
                rate=float(np.clip(
                    mod_a.rate * random.uniform(0.9, 1.1), rate_lo, rate_hi)),
                depth=float(np.clip(
                    mod_a.depth * random.uniform(0.9, 1.1), depth_lo, depth_hi)),
            )
        return self._select_modulation(profile, 0.5, prev_segment, 'b')

    def _select_duty_cycle(self, cfg: GeneratorConfig, intensity: float) -> float:
        """Select duty cycle based on intensity."""
        base = 0.3 + 0.4 * intensity  # Higher intensity → wider pulses
        variation = cfg.randomness * 0.2
        return np.clip(base + random.uniform(-variation, variation), 0.1, 0.9)

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
    )

    generator = SessionGenerator(config)
    return generator.generate()
