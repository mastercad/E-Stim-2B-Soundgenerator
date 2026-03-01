"""
Pattern and Segment definitions for E-Stim 2B sessions.

A Pattern defines how a signal behaves over a time segment:
- Waveform type, frequency, amplitude for each channel
- Modulation settings
- Transition behavior (how to blend into the next pattern)
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any

from .waveforms import WaveformType
from .modulation import ModulationType, ModulationParams, EnvelopeADSR


class TransitionType(Enum):
    """How to transition between patterns."""
    INSTANT = "instant"       # Hard cut
    CROSSFADE = "crossfade"   # Smooth blend
    FADE_OUT_IN = "fade_out_in"  # Fade out then fade in


@dataclass
class ChannelConfig:
    """Configuration for a single E-Stim channel."""
    waveform: WaveformType = WaveformType.SINE
    frequency: float = 80.0       # Hz
    amplitude: float = 0.7        # [0.0, 1.0]
    duty_cycle: float = 0.5       # For pulse waveform
    phase_offset: float = 0.0     # Radians

    # Frequency range for dynamic variation
    freq_min: Optional[float] = None
    freq_max: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "waveform": self.waveform.value,
            "frequency": self.frequency,
            "amplitude": self.amplitude,
            "duty_cycle": self.duty_cycle,
            "phase_offset": self.phase_offset,
            "freq_min": self.freq_min,
            "freq_max": self.freq_max,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelConfig":
        return cls(
            waveform=WaveformType(data.get("waveform", "sine")),
            frequency=data.get("frequency", 80.0),
            amplitude=data.get("amplitude", 0.7),
            duty_cycle=data.get("duty_cycle", 0.5),
            phase_offset=data.get("phase_offset", 0.0),
            freq_min=data.get("freq_min"),
            freq_max=data.get("freq_max"),
        )


@dataclass
class PatternSegment:
    """
    A segment in a session timeline.

    Represents a time period with specific stimulation parameters
    for both channels.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Segment"
    duration: float = 10.0  # Duration in seconds

    # Channel configurations
    channel_a: ChannelConfig = field(default_factory=ChannelConfig)
    channel_b: ChannelConfig = field(default_factory=ChannelConfig)

    # Modulation
    modulation_a: ModulationParams = field(default_factory=ModulationParams)
    modulation_b: ModulationParams = field(default_factory=ModulationParams)

    # Envelope
    use_envelope: bool = False
    envelope: EnvelopeADSR = field(default_factory=EnvelopeADSR)

    # Transition to next segment
    transition: TransitionType = TransitionType.CROSSFADE
    transition_duration: float = 1.0  # Seconds for transition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "duration": self.duration,
            "channel_a": self.channel_a.to_dict(),
            "channel_b": self.channel_b.to_dict(),
            "modulation_a": {
                "type": self.modulation_a.mod_type.value,
                "rate": self.modulation_a.rate,
                "depth": self.modulation_a.depth,
            },
            "modulation_b": {
                "type": self.modulation_b.mod_type.value,
                "rate": self.modulation_b.rate,
                "depth": self.modulation_b.depth,
            },
            "use_envelope": self.use_envelope,
            "envelope": {
                "attack": self.envelope.attack,
                "decay": self.envelope.decay,
                "sustain": self.envelope.sustain,
                "release": self.envelope.release,
            },
            "transition": self.transition.value,
            "transition_duration": self.transition_duration,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternSegment":
        mod_a_data = data.get("modulation_a", {})
        mod_b_data = data.get("modulation_b", {})
        env_data = data.get("envelope", {})

        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Segment"),
            duration=data.get("duration", 10.0),
            channel_a=ChannelConfig.from_dict(data.get("channel_a", {})),
            channel_b=ChannelConfig.from_dict(data.get("channel_b", {})),
            modulation_a=ModulationParams(
                mod_type=ModulationType(mod_a_data.get("type", "none")),
                rate=mod_a_data.get("rate", 1.0),
                depth=mod_a_data.get("depth", 0.5),
            ),
            modulation_b=ModulationParams(
                mod_type=ModulationType(mod_b_data.get("type", "none")),
                rate=mod_b_data.get("rate", 1.0),
                depth=mod_b_data.get("depth", 0.5),
            ),
            use_envelope=data.get("use_envelope", False),
            envelope=EnvelopeADSR(
                attack=env_data.get("attack", 0.1),
                decay=env_data.get("decay", 0.1),
                sustain=env_data.get("sustain", 0.7),
                release=env_data.get("release", 0.2),
            ),
            transition=TransitionType(data.get("transition", "crossfade")),
            transition_duration=data.get("transition_duration", 1.0),
        )


# ─── Preset Patterns ──────────────────────────────────────────────

def create_preset_patterns() -> Dict[str, PatternSegment]:
    """Create a library of preset patterns optimized for E-Stim 2B."""

    presets = {}

    # Gentle Pulse - Low frequency, soft sensation
    presets["gentle_pulse"] = PatternSegment(
        name="Sanfter Puls",
        duration=30.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.SINE, frequency=30.0, amplitude=0.5
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.SINE, frequency=30.0, amplitude=0.5
        ),
        modulation_a=ModulationParams(
            mod_type=ModulationType.TREMOLO, rate=0.5, depth=0.3
        ),
        modulation_b=ModulationParams(
            mod_type=ModulationType.TREMOLO, rate=0.5, depth=0.3
        ),
    )

    # Rhythmic Waves - Alternating channels
    presets["rhythmic_waves"] = PatternSegment(
        name="Rhythmische Wellen",
        duration=30.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.SINE, frequency=60.0, amplitude=0.7
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.SINE, frequency=60.0, amplitude=0.7,
            phase_offset=3.14159  # Phase shifted for alternating feel
        ),
        modulation_a=ModulationParams(
            mod_type=ModulationType.WAVE, rate=0.3, depth=0.6
        ),
        modulation_b=ModulationParams(
            mod_type=ModulationType.WAVE, rate=0.3, depth=0.6
        ),
    )

    # Sharp Tingle - Higher frequency square wave
    presets["sharp_tingle"] = PatternSegment(
        name="Scharfes Kribbeln",
        duration=20.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.SQUARE, frequency=150.0, amplitude=0.6
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.SQUARE, frequency=160.0, amplitude=0.6
        ),
        modulation_a=ModulationParams(
            mod_type=ModulationType.AM, rate=2.0, depth=0.4
        ),
        modulation_b=ModulationParams(
            mod_type=ModulationType.AM, rate=2.0, depth=0.4
        ),
    )

    # Deep Throb - Low frequency with strong modulation
    presets["deep_throb"] = PatternSegment(
        name="Tiefes Pochen",
        duration=30.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.TRIANGLE, frequency=15.0, amplitude=0.8
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.TRIANGLE, frequency=15.0, amplitude=0.8
        ),
        modulation_a=ModulationParams(
            mod_type=ModulationType.TREMOLO, rate=1.0, depth=0.8
        ),
        modulation_b=ModulationParams(
            mod_type=ModulationType.TREMOLO, rate=1.0, depth=0.8
        ),
    )

    # Climbing Intensity - Ramp up
    presets["climbing"] = PatternSegment(
        name="Aufsteigend",
        duration=60.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.SINE, frequency=80.0, amplitude=0.9
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.SINE, frequency=80.0, amplitude=0.9
        ),
        modulation_a=ModulationParams(
            mod_type=ModulationType.RAMP_UP, rate=1.0, depth=0.8
        ),
        modulation_b=ModulationParams(
            mod_type=ModulationType.RAMP_UP, rate=1.0, depth=0.8
        ),
    )

    # Burst Fire - Short pulses
    presets["burst_fire"] = PatternSegment(
        name="Stoßfeuer",
        duration=20.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.BURST, frequency=100.0, amplitude=0.7,
            duty_cycle=0.3
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.BURST, frequency=100.0, amplitude=0.7,
            duty_cycle=0.3
        ),
    )

    # Frequency Sweep
    presets["sweep"] = PatternSegment(
        name="Frequenz-Sweep",
        duration=30.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.CHIRP, frequency=20.0, amplitude=0.7,
            freq_min=20.0, freq_max=200.0
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.CHIRP, frequency=20.0, amplitude=0.7,
            freq_min=20.0, freq_max=200.0
        ),
    )

    # Asymmetric - Different patterns per channel
    presets["asymmetric"] = PatternSegment(
        name="Asymmetrisch",
        duration=30.0,
        channel_a=ChannelConfig(
            waveform=WaveformType.SINE, frequency=50.0, amplitude=0.6
        ),
        channel_b=ChannelConfig(
            waveform=WaveformType.SQUARE, frequency=80.0, amplitude=0.5
        ),
        modulation_a=ModulationParams(
            mod_type=ModulationType.TREMOLO, rate=0.5, depth=0.5
        ),
        modulation_b=ModulationParams(
            mod_type=ModulationType.AM, rate=1.5, depth=0.4
        ),
    )

    return presets
