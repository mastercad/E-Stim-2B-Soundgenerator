# E-Stim 2B Sound Generator - Core Module
"""
Core audio engine for generating E-Stim 2B compatible audio signals.

The E-Stim 2B accepts stereo audio input:
- Left channel  → Channel A
- Right channel → Channel B

Signal characteristics:
- Amplitude controls stimulation intensity
- Frequency range for sensation: ~2 Hz to ~300 Hz
- Audio carrier frequencies can be higher
- Both channels are independently controllable
"""

__version__ = "1.0.0"
