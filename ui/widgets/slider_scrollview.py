"""
Custom ScrollView and Slider for reliable desktop and mobile interaction.

Fixes two Kivy issues:
1. ScrollView steals touch events from Slider children (click+drag broken)
2. Coordinate mismatch: widget.collide_point uses parent-space coords but
   touch.pos is in window-space — diverges by scroll offset inside ScrollView

On Android/touch, distinguishes horizontal slider drags from vertical scrolls
using a directional threshold before committing to either action.

Also adds mouse-wheel support for sliders on desktop.
"""

from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivy.utils import platform
from kivymd.uix.slider import MDSlider

# Vertical padding around slider for easier hit detection (px)
_SLIDER_PAD_Y = 20
# Movement threshold (in pixels) before committing to scroll vs slider
_DIRECTION_THRESHOLD = 12


class SliderFriendlyScrollView(ScrollView):
    """
    A ScrollView that properly detects slider touches using coordinate
    transforms, adds mouse-wheel value changes, and prevents the
    ScrollView from grabbing slider drags.

    On touch devices, uses a direction-detection phase: the first few
    pixels of movement decide whether the gesture is a horizontal slider
    drag or a vertical page scroll.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_slider = None    # currently-touched slider reference
        self._pending_slider = None   # slider under finger, awaiting direction
        self._touch_start = None      # (x, y) of initial touch
        self._decided = False         # True once direction is resolved
        self.scroll_type = ['bars', 'content']
        self.bar_width = dp(4)

    # ── helpers ────────────────────────────────────────────────────

    def _slider_at(self, touch):
        """Return the MDSlider under *touch* (window coords), or None.

        Uses to_widget() for correct coordinate conversion even when
        the content is scrolled.
        """
        for widget in self.walk(restrict=True):
            if isinstance(widget, MDSlider):
                # convert window coords → widget-local coords
                lx, ly = widget.to_widget(*touch.pos)
                pad = dp(_SLIDER_PAD_Y)
                if (-pad <= lx <= widget.width + pad and
                        -pad <= ly <= widget.height + pad):
                    return widget
        return None

    @staticmethod
    def _is_mouse(touch):
        """Return True if this is a desktop mouse event (not touch)."""
        return getattr(touch, 'button', None) is not None

    @staticmethod
    def _scroll_slider(slider, direction):
        """Nudge *slider* value up/down by 2 % of its range."""
        step = (slider.max - slider.min) * 0.02
        if direction == 'up':
            slider.value = min(slider.max, slider.value + step)
        else:
            slider.value = max(slider.min, slider.value - step)

    @staticmethod
    def _move_slider_to(slider, touch):
        """Set *slider* value from touch x in widget-local space."""
        lx, _ = slider.to_widget(*touch.pos)
        # padding on the actual slider track
        pad = dp(16)
        usable = slider.width - 2 * pad
        if usable <= 0:
            return
        ratio = max(0.0, min(1.0, (lx - pad) / usable))
        slider.value = slider.min + ratio * (slider.max - slider.min)

    # ── touch dispatch ────────────────────────────────────────────

    def on_touch_down(self, touch):
        slider = self._slider_at(touch)

        if slider is not None:
            # Mouse-wheel on a slider → change value, don't scroll page
            btn = getattr(touch, 'button', None)
            if btn in ('scrollup', 'scrolldown'):
                self._scroll_slider(slider,
                                    'up' if btn == 'scrollup' else 'down')
                return True  # consumed

            # Desktop mouse click → commit to slider immediately
            if self._is_mouse(touch):
                self._active_slider = slider
                self._pending_slider = None
                self._decided = True
                touch.grab(self)
                self._move_slider_to(slider, touch)
                return True

            # Touch device → enter direction-detection phase
            self._pending_slider = slider
            self._touch_start = touch.pos
            self._decided = False
            self._active_slider = None
            touch.grab(self)
            # Don't move the slider yet; wait for direction
            return True

        # No slider hit → normal ScrollView behaviour
        self._active_slider = None
        self._pending_slider = None
        self._decided = False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)

        # Already committed to slider
        if self._decided and self._active_slider is not None:
            self._move_slider_to(self._active_slider, touch)
            return True

        # Already committed to scroll (pending was cleared)
        if self._decided and self._active_slider is None:
            return super().on_touch_move(touch)

        # Still in direction-detection phase
        if self._pending_slider and self._touch_start:
            dx = abs(touch.pos[0] - self._touch_start[0])
            dy = abs(touch.pos[1] - self._touch_start[1])

            if dx > _DIRECTION_THRESHOLD or dy > _DIRECTION_THRESHOLD:
                self._decided = True
                if dx >= dy:
                    # Horizontal → slider drag
                    self._active_slider = self._pending_slider
                    self._pending_slider = None
                    self._move_slider_to(self._active_slider, touch)
                    return True
                else:
                    # Vertical → scroll — hand off to ScrollView
                    self._pending_slider = None
                    self._active_slider = None
                    touch.ungrab(self)
                    # Re-dispatch so ScrollView picks it up
                    return super().on_touch_down(touch)

            # Below threshold — swallow the move but do nothing yet
            return True

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            if self._active_slider is not None:
                self._move_slider_to(self._active_slider, touch)
                touch.ungrab(self)
                self._active_slider = None
                self._pending_slider = None
                self._decided = False
                return True

            if self._pending_slider is not None and not self._decided:
                # Short tap on a slider — treat as a direct set
                self._move_slider_to(self._pending_slider, touch)
                touch.ungrab(self)
                self._pending_slider = None
                self._decided = False
                return True

            touch.ungrab(self)
            self._pending_slider = None
            self._decided = False

        return super().on_touch_up(touch)
