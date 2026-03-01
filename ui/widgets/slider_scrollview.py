"""
Custom ScrollView with desktop-mouse slider enhancements.

Desktop (mouse):
  - Click-to-set on sliders (using correct coordinate transforms inside
    scrolled content)
  - Mouse-wheel on sliders nudges value ±2 %

Touch / Android:
  - Relies entirely on Kivy's native ScrollView touch handling which
    correctly arbitrates between vertical scrolling and child widget
    interaction (sliders, buttons, etc.) through its built-in
    scroll_timeout / scroll_distance mechanism.
"""

from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivymd.uix.slider import MDSlider

# Vertical padding around slider for easier mouse hit detection (px)
_SLIDER_PAD_Y = 20


class SliderFriendlyScrollView(ScrollView):
    """
    ScrollView that adds desktop-mouse slider improvements without
    interfering with touch-device scrolling.

    On Android / touchscreens the standard Kivy ScrollView remains in
    charge — it already handles the "scroll vs child drag" conflict
    through its timeout mechanism, so touching *anywhere* on the screen
    (cards, labels, sliders …) allows vertical scrolling.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_slider = None          # slider grabbed by mouse
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
        pad = dp(16)
        usable = slider.width - 2 * pad
        if usable <= 0:
            return
        ratio = max(0.0, min(1.0, (lx - pad) / usable))
        slider.value = slider.min + ratio * (slider.max - slider.min)

    # ── touch dispatch ────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        # ── Desktop mouse: enhanced slider interaction ────────────
        if self._is_mouse(touch):
            slider = self._slider_at(touch)
            if slider:
                btn = getattr(touch, 'button', None)
                if btn in ('scrollup', 'scrolldown'):
                    self._scroll_slider(
                        slider, 'up' if btn == 'scrollup' else 'down')
                    return True
                # Left-click → jump slider to position
                self._active_slider = slider
                touch.grab(self)
                self._move_slider_to(slider, touch)
                return True

        # ── Touch device (or mouse on non-slider area) ───────────
        # Let Kivy's standard ScrollView handle everything.  Its
        # built-in scroll_timeout / scroll_distance mechanism will:
        #   • scroll the page on vertical finger movement
        #   • let sliders/buttons/cards handle taps & horizontal drags
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        # Desktop slider drag
        if touch.grab_current is self and self._active_slider is not None:
            self._move_slider_to(self._active_slider, touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        # Desktop slider release
        if touch.grab_current is self and self._active_slider is not None:
            self._move_slider_to(self._active_slider, touch)
            touch.ungrab(self)
            self._active_slider = None
            return True
        return super().on_touch_up(touch)
