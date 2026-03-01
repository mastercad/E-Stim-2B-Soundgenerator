"""
CardBox — A scroll-safe card-like container.

MDCard inherits from ButtonBehavior, which calls touch.grab(self) on
every touch and returns True.  This prevents Kivy's ScrollView from
ever seeing the touch event, completely blocking scroll on Android.

CardBox is a plain BoxLayout with a rounded, coloured background drawn
via Canvas instructions.  It looks like an MDCard but has **zero** touch
handling of its own, so ScrollView scrolling works everywhere.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty


class CardBox(BoxLayout):
    """Styled card container that does NOT consume touch events."""

    bg_color = ListProperty([0.15, 0.15, 0.18, 1])
    radius = ListProperty([dp(8)])

    def __init__(self, **kwargs):
        # Pop MDCard-style kwargs that Canvas doesn't understand
        bg = kwargs.pop('md_bg_color', None)
        rad = kwargs.pop('card_radius', None)
        super().__init__(**kwargs)
        if bg is not None:
            self.bg_color = bg
        if rad is not None:
            self.radius = rad

        with self.canvas.before:
            self._bg_color_instr = Color(*self.bg_color)
            self._bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=self.radius,
            )
        self.bind(pos=self._update_rect, size=self._update_rect)
        self.bind(bg_color=self._update_color, radius=self._update_radius)

    def _update_rect(self, *_args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _update_color(self, *_args):
        self._bg_color_instr.rgba = self.bg_color

    def _update_radius(self, *_args):
        self._bg_rect.radius = self.radius
