"""
Waveform Display Widget - Real-time visualization of audio waveforms.

Performance-optimised: uses numpy for all point computation, throttles
redraws, and caches grid instructions so that slider interaction and
audio playback can coexist without stutter.
"""

from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle, InstructionGroup
from kivy.properties import NumericProperty, BooleanProperty
from kivy.clock import Clock
import numpy as np
from time import perf_counter


# Maximum number of display points (keeps canvas instructions cheap)
_MAX_POINTS = 200


class WaveformDisplay(Widget):
    """
    Widget that displays a waveform visualization.

    Can show both pre-rendered waveforms and real-time audio data.
    Displays stereo as two overlapping waveforms (Channel A: blue, Channel B: red).
    """

    # Visual properties
    line_width = NumericProperty(1.5)
    show_grid = BooleanProperty(True)
    show_stereo = BooleanProperty(True)

    # Colors (RGBA)
    color_left = [0.2, 0.6, 1.0, 1.0]    # Blue for Channel A
    color_right = [1.0, 0.3, 0.3, 0.8]    # Red for Channel B
    color_bg = [0.12, 0.12, 0.15, 1.0]     # Dark background
    color_grid = [0.25, 0.25, 0.3, 0.5]    # Grid lines
    color_center = [0.3, 0.3, 0.35, 0.8]   # Center line

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Raw numpy data – kept as arrays, never converted to Python lists
        self._np_left: np.ndarray | None = None
        self._np_right: np.ndarray | None = None

        # Redraw throttling – at most one redraw per frame, max ~30 FPS
        self._redraw_scheduled = False
        self._last_redraw: float = 0.0
        self._MIN_REDRAW_INTERVAL = 1.0 / 30  # seconds

        # Cached grid instruction group (rebuilt only on resize)
        self._grid_group: InstructionGroup | None = None
        self._grid_size = (0, 0)
        self._grid_pos = (0, 0)

        self.bind(pos=self._on_layout, size=self._on_layout)
        Clock.schedule_once(self._deferred_init, 0)

    def _deferred_init(self, dt):
        self._invalidate_grid()
        self._schedule_redraw()

    def _on_layout(self, *_args):
        """Reacts to position / size changes."""
        self._invalidate_grid()
        self._schedule_redraw()

    # ── Public API ───────────────────────────────────────────────────

    def set_data(self, left_data, right_data=None):
        """Set waveform data for display (accepts numpy arrays or lists)."""
        if isinstance(left_data, np.ndarray):
            self._np_left = left_data
        elif left_data is not None:
            self._np_left = np.asarray(left_data, dtype=np.float32)
        else:
            self._np_left = None

        if right_data is not None:
            if isinstance(right_data, np.ndarray):
                self._np_right = right_data
            else:
                self._np_right = np.asarray(right_data, dtype=np.float32)
        else:
            self._np_right = None

        self._schedule_redraw()

    def clear_data(self):
        """Clear waveform display."""
        self._np_left = None
        self._np_right = None
        self._schedule_redraw()

    # ── Throttled redraw ─────────────────────────────────────────────

    def _schedule_redraw(self):
        """Request a redraw, but coalesce rapid requests into one."""
        if self._redraw_scheduled:
            return
        now = perf_counter()
        elapsed = now - self._last_redraw
        if elapsed >= self._MIN_REDRAW_INTERVAL:
            # Enough time has passed – draw on the next frame
            Clock.schedule_once(self._do_redraw, 0)
        else:
            # Too soon – schedule for the remaining interval
            Clock.schedule_once(self._do_redraw, self._MIN_REDRAW_INTERVAL - elapsed)
        self._redraw_scheduled = True

    def _do_redraw(self, _dt=None):
        """Actual canvas update."""
        self._redraw_scheduled = False
        self._last_redraw = perf_counter()

        self.canvas.clear()
        with self.canvas:
            # Background
            Color(*self.color_bg)
            Rectangle(pos=self.pos, size=self.size)

        # Grid (cached instruction group)
        if self.show_grid:
            grid = self._get_grid_group()
            self.canvas.add(grid)

        with self.canvas:
            # Center line
            Color(*self.color_center)
            cy = self.y + self.height / 2
            Line(points=[self.x, cy, self.x + self.width, cy], width=1)

            # Channel A (left)
            if self._np_left is not None and len(self._np_left) > 1:
                Color(*self.color_left)
                pts = self._data_to_points_fast(self._np_left)
                if pts is not None:
                    Line(points=pts, width=self.line_width)

            # Channel B (right)
            if self.show_stereo and self._np_right is not None and len(self._np_right) > 1:
                Color(*self.color_right)
                pts = self._data_to_points_fast(self._np_right)
                if pts is not None:
                    Line(points=pts, width=self.line_width)

    # ── Vectorised point computation ─────────────────────────────────

    def _data_to_points_fast(self, data: np.ndarray):
        """Convert numpy waveform data to a flat list for Kivy Line, using numpy only."""
        n = len(data)
        if n < 2 or self.width < 2:
            return None

        num_points = min(n, _MAX_POINTS, int(self.width))
        if num_points < 2:
            return None

        # Down-sample with evenly spaced indices
        if n > num_points:
            indices = np.linspace(0, n - 1, num_points, dtype=np.intp)
            samples = data[indices]
        else:
            samples = data
            num_points = n

        # Vectorised x / y computation
        xs = self.x + np.linspace(0.0, self.width, num_points, dtype=np.float32)
        mid = self.y + self.height * 0.5
        ys = mid + samples * (self.height * 0.45)  # 0.45 = 0.5 * 0.9 scaling

        # Interleave x, y into flat array: [x0, y0, x1, y1, …]
        pts = np.empty(num_points * 2, dtype=np.float32)
        pts[0::2] = xs
        pts[1::2] = ys
        return pts.tolist()  # Kivy needs a Python sequence, but this is a single bulk tolist()

    # ── Grid caching ─────────────────────────────────────────────────

    def _invalidate_grid(self):
        self._grid_group = None

    def _get_grid_group(self) -> InstructionGroup:
        """Return (and cache) the grid instruction group."""
        cur_size = (self.width, self.height)
        cur_pos = (self.x, self.y)
        if self._grid_group is not None and self._grid_size == cur_size and self._grid_pos == cur_pos:
            return self._grid_group

        grp = InstructionGroup()
        grp.add(Color(*self.color_grid))

        # Horizontal grid lines (amplitude)
        for frac in (0.25, 0.75):
            gy = self.y + self.height * frac
            grp.add(Line(points=[self.x, gy, self.x + self.width, gy], width=0.5))

        # Vertical grid lines (time)
        num_vlines = 8
        for i in range(1, num_vlines):
            gx = self.x + self.width * i / num_vlines
            grp.add(Line(points=[gx, self.y, gx, self.y + self.height], width=0.5))

        self._grid_group = grp
        self._grid_size = cur_size
        self._grid_pos = cur_pos
        return grp
