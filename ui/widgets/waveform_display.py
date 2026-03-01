"""
Waveform Display Widget - Real-time visualization of audio waveforms.
"""

from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import ListProperty, NumericProperty, BooleanProperty
from kivy.clock import Clock
import numpy as np


class WaveformDisplay(Widget):
    """
    Widget that displays a waveform visualization.

    Can show both pre-rendered waveforms and real-time audio data.
    Displays stereo as two overlapping waveforms (Channel A: blue, Channel B: red).
    """

    # Waveform data (list of float values -1.0 to 1.0)
    data_left = ListProperty([])
    data_right = ListProperty([])

    # Visual properties
    line_width = NumericProperty(1.5)
    show_grid = BooleanProperty(True)
    show_stereo = BooleanProperty(True)

    # Colors (RGBA)
    color_left = ListProperty([0.2, 0.6, 1.0, 1.0])   # Blue for Channel A
    color_right = ListProperty([1.0, 0.3, 0.3, 0.8])   # Red for Channel B
    color_bg = ListProperty([0.12, 0.12, 0.15, 1.0])    # Dark background
    color_grid = ListProperty([0.25, 0.25, 0.3, 0.5])   # Grid lines
    color_center = ListProperty([0.3, 0.3, 0.35, 0.8])  # Center line

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._update, size=self._update)
        self.bind(data_left=self._update, data_right=self._update)
        Clock.schedule_once(self._update, 0)

    def _update(self, *args):
        """Redraw the waveform display."""
        self.canvas.clear()
        with self.canvas:
            # Background
            Color(*self.color_bg)
            Rectangle(pos=self.pos, size=self.size)

            # Grid
            if self.show_grid:
                self._draw_grid()

            # Center line
            Color(*self.color_center)
            cy = self.y + self.height / 2
            Line(points=[self.x, cy, self.x + self.width, cy], width=1)

            # Waveform Channel A (Left)
            if self.data_left:
                Color(*self.color_left)
                points = self._data_to_points(self.data_left)
                if len(points) >= 4:
                    Line(points=points, width=self.line_width)

            # Waveform Channel B (Right)
            if self.show_stereo and self.data_right:
                Color(*self.color_right)
                points = self._data_to_points(self.data_right)
                if len(points) >= 4:
                    Line(points=points, width=self.line_width)

    def _draw_grid(self):
        """Draw background grid lines."""
        Color(*self.color_grid)

        # Horizontal grid lines (amplitude)
        for frac in [0.25, 0.75]:
            gy = self.y + self.height * frac
            Line(points=[self.x, gy, self.x + self.width, gy], width=0.5)

        # Vertical grid lines (time)
        num_vlines = 8
        for i in range(1, num_vlines):
            gx = self.x + self.width * i / num_vlines
            Line(points=[gx, self.y, gx, self.y + self.height], width=0.5)

    def _data_to_points(self, data):
        """Convert waveform data to Kivy Line points."""
        if not data:
            return []

        num_points = min(len(data), int(self.width))
        if num_points < 2:
            return []

        # Downsample or use as-is
        if len(data) > num_points:
            indices = np.linspace(0, len(data) - 1, num_points, dtype=int)
            samples = [data[i] for i in indices]
        else:
            samples = list(data)
            num_points = len(samples)

        points = []
        for i, val in enumerate(samples):
            x = self.x + (i / (num_points - 1)) * self.width
            y = self.y + self.height / 2 + val * self.height / 2 * 0.9
            points.extend([x, y])

        return points

    def set_data(self, left_data, right_data=None):
        """Set waveform data for display."""
        if isinstance(left_data, np.ndarray):
            self.data_left = left_data.tolist()
        else:
            self.data_left = list(left_data)

        if right_data is not None:
            if isinstance(right_data, np.ndarray):
                self.data_right = right_data.tolist()
            else:
                self.data_right = list(right_data)

    def clear_data(self):
        """Clear waveform display."""
        self.data_left = []
        self.data_right = []
