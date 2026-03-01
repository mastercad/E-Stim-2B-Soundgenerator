"""
Scroll-friendly ScrollView for pages with sliders.

All touch/scroll handling is delegated to Kivy's native ScrollView
which correctly arbitrates between vertical page scrolling and child
widget interaction (sliders, buttons, cards) through its built-in
scroll_timeout / scroll_distance mechanism.

The only custom behaviour added is desktop mouse-wheel support for
nudging slider values.
"""

from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp
from kivymd.uix.slider import MDSlider


class SliderFriendlyScrollView(ScrollView):
    """ScrollView with mouse-wheel slider support for desktop.

    Touch handling is 100 % native Kivy — no overrides.  This means:
      * Android/touch: vertical finger drag scrolls the page even on
        top of cards, labels, sliders and buttons.
      * Desktop: click-drag scrolls, and sliders respond to clicks
        natively via MDSlider's own touch handling.
      * Mouse-wheel over a slider nudges its value instead of scrolling
        the page (desktop convenience).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll_type = ['bars', 'content']
        self.bar_width = dp(4)
        self.do_scroll_x = False          # vertical scrolling only
        self.scroll_distance = dp(12)     # px before scroll starts
        self.scroll_timeout = 80          # ms before dispatching to children

    # ── mouse-wheel on sliders (desktop only) ─────────────────────

    def on_touch_down(self, touch):
        btn = getattr(touch, 'button', None)
        if btn in ('scrollup', 'scrolldown') and self.collide_point(*touch.pos):
            # Check if a slider is directly under the cursor
            for widget in self.walk(restrict=True):
                if isinstance(widget, MDSlider):
                    lx, ly = widget.to_widget(*touch.pos)
                    if 0 <= lx <= widget.width and 0 <= ly <= widget.height:
                        step = (widget.max - widget.min) * 0.02
                        if btn == 'scrollup':
                            widget.value = min(widget.max, widget.value + step)
                        else:
                            widget.value = max(widget.min, widget.value - step)
                        return True   # consumed — don't scroll page

        # Everything else: native Kivy ScrollView handles it
        return super().on_touch_down(touch)
