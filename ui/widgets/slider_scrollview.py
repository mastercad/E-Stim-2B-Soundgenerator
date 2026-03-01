"""
Custom ScrollView and Slider for reliable desktop and mobile interaction.

Fixes two Kivy issues:
1. ScrollView steals touch events from Slider children (click+drag broken)
2. Coordinate mismatch: widget.collide_point uses parent-space coords but
   touch.pos is in window-space — diverges by scroll offset inside ScrollView

Also adds mouse-wheel support for sliders on desktop.
"""

from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivymd.uix.slider import MDSlider

# Vertical padding around slider for easier hit detection (px)
_SLIDER_PAD_Y = 20


class SliderFriendlyScrollView(ScrollView):
    """
    A ScrollView that properly detects slider touches using coordinate
    transforms, adds mouse-wheel value changes, and prevents the
    ScrollView from grabbing slider drags.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_slider = None  # currently-touched slider reference
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

            # Click / tap → grab so ScrollView can't steal it
            self._active_slider = slider
            touch.grab(self)
            self._move_slider_to(slider, touch)
            return True

        # No slider hit → normal ScrollView behaviour
        self._active_slider = None
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._active_slider is not None:
            self._move_slider_to(self._active_slider, touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self and self._active_slider is not None:
            self._move_slider_to(self._active_slider, touch)
            touch.ungrab(self)
            self._active_slider = None
            return True
        return super().on_touch_up(touch)
