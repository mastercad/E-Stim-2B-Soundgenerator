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

        # Generate each segment
        for i in range(num_phases):
            segment = self._generate_segment(
                cfg=cfg,
                index=i,
                total_phases=num_phases,
                intensity=intensities[i],
                duration=durations[i],
            )
            session.add_segment(segment)

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

    def _generate_segment(
        self,
        cfg: GeneratorConfig,
        index: int,
        total_phases: int,
        intensity: float,
        duration: float,
    ) -> PatternSegment:
        """Generate a single segment based on configuration and intensity."""

        # Select waveform based on style
        waveform_a = self._select_waveform(cfg)
        waveform_b = self._select_waveform_b(cfg, waveform_a)

        # Select frequency
        freq_a = self._select_frequency(cfg, intensity)
        freq_b = self._select_frequency_b(cfg, freq_a)

        # Select modulation
        mod_a = self._select_modulation(cfg, intensity)
        mod_b = self._select_modulation_b(cfg, mod_a)

        # Determine duty cycle for pulse waveforms
        duty_a = self._select_duty_cycle(cfg, intensity)
        duty_b = duty_a if cfg.channel_symmetry > random.random() else self._select_duty_cycle(cfg, intensity)

        # Create envelope if enabled
        use_envelope = cfg.use_envelopes and random.random() < cfg.envelope_probability
        envelope = self._generate_envelope(cfg, duration, intensity) if use_envelope else EnvelopeADSR()

        # Transition
        is_last = index == total_phases - 1
        transition = TransitionType.CROSSFADE if not is_last else TransitionType.FADE_OUT_IN

        # Phase names
        phase_names = self._get_phase_name(index, total_phases, cfg.style)

        segment = PatternSegment(
            name=phase_names,
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
                amplitude=intensity * (0.8 + random.random() * 0.2 if cfg.channel_symmetry < 1.0 else 1.0),
                duty_cycle=duty_b,
            ),
            modulation_a=mod_a,
            modulation_b=mod_b,
            use_envelope=use_envelope,
            envelope=envelope,
            transition=transition,
            transition_duration=min(cfg.transition_duration, duration * 0.3),
        )

        return segment

    def _select_waveform(self, cfg: GeneratorConfig) -> WaveformType:
        """Select a waveform based on style and preferences."""
        style_weights = {
            SessionStyle.RELAXATION: {
                WaveformType.SINE: 5, WaveformType.TRIANGLE: 3,
                WaveformType.SAWTOOTH: 1, WaveformType.SQUARE: 1, WaveformType.PULSE: 1,
            },
            SessionStyle.RHYTHMIC: {
                WaveformType.SINE: 2, WaveformType.SQUARE: 3,
                WaveformType.PULSE: 3, WaveformType.TRIANGLE: 2, WaveformType.SAWTOOTH: 2,
            },
            SessionStyle.INTENSE: {
                WaveformType.SQUARE: 3, WaveformType.SAWTOOTH: 3,
                WaveformType.PULSE: 2, WaveformType.SINE: 1, WaveformType.TRIANGLE: 1,
            },
            SessionStyle.TEASING: {
                WaveformType.SINE: 3, WaveformType.PULSE: 3,
                WaveformType.TRIANGLE: 2, WaveformType.SQUARE: 2, WaveformType.SAWTOOTH: 1,
            },
            SessionStyle.MEDITATION: {
                WaveformType.SINE: 6, WaveformType.TRIANGLE: 3,
                WaveformType.SAWTOOTH: 1, WaveformType.SQUARE: 0, WaveformType.PULSE: 0,
            },
            SessionStyle.ADVENTURE: {
                WaveformType.SINE: 2, WaveformType.SQUARE: 2, WaveformType.TRIANGLE: 2,
                WaveformType.SAWTOOTH: 2, WaveformType.PULSE: 2,
            },
        }

        weights = style_weights.get(cfg.style, {})
        # Filter to allowed waveforms
        choices = []
        probs = []
        for wf in cfg.allowed_waveforms:
            choices.append(wf)
            probs.append(weights.get(wf, 1))

        if not choices:
            return WaveformType.SINE

        total = sum(probs)
        probs = [p / total for p in probs]
        return random.choices(choices, weights=probs, k=1)[0]

    def _select_waveform_b(self, cfg: GeneratorConfig, waveform_a: WaveformType) -> WaveformType:
        """Select waveform for channel B based on symmetry setting."""
        if random.random() < cfg.channel_symmetry:
            return waveform_a
        return self._select_waveform(cfg)

    def _select_frequency(self, cfg: GeneratorConfig, intensity: float) -> float:
        """Select a frequency based on preferences and intensity."""
        if cfg.preferred_frequencies and random.random() > cfg.randomness:
            # Use a preferred frequency with some variation
            base = random.choice(cfg.preferred_frequencies)
            variation = base * cfg.randomness * 0.2
            freq = base + random.uniform(-variation, variation)
        else:
            # Random within range, biased by intensity
            low, high = cfg.freq_range
            # Higher intensity tends toward higher frequencies
            center = low + (high - low) * (0.3 + 0.7 * intensity)
            spread = (high - low) * 0.2
            freq = random.gauss(center, spread)

        return np.clip(freq, cfg.freq_range[0], cfg.freq_range[1])

    def _select_frequency_b(self, cfg: GeneratorConfig, freq_a: float) -> float:
        """Select frequency for channel B."""
        if random.random() < cfg.channel_symmetry:
            # Similar frequency with small detuning (creates interesting beats)
            detune = random.uniform(-5, 5)
            return max(cfg.freq_range[0], freq_a + detune)
        return self._select_frequency(cfg, 0.5)

    def _select_modulation(self, cfg: GeneratorConfig, intensity: float) -> ModulationParams:
        """Select modulation parameters."""
        if random.random() > cfg.modulation_probability:
            return ModulationParams(mod_type=ModulationType.NONE)

        available = [m for m in cfg.allowed_modulations if m != ModulationType.NONE]
        if not available:
            return ModulationParams(mod_type=ModulationType.NONE)

        mod_type = random.choice(available)
        rate = random.uniform(0.2, 3.0)
        depth = random.uniform(0.2, 0.8) * (0.5 + 0.5 * intensity)

        return ModulationParams(mod_type=mod_type, rate=rate, depth=depth)

    def _select_modulation_b(self, cfg: GeneratorConfig, mod_a: ModulationParams) -> ModulationParams:
        """Select modulation for channel B."""
        if random.random() < cfg.channel_symmetry:
            return ModulationParams(
                mod_type=mod_a.mod_type,
                rate=mod_a.rate * random.uniform(0.9, 1.1),
                depth=mod_a.depth * random.uniform(0.9, 1.1),
            )
        return self._select_modulation(cfg, 0.5)

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
