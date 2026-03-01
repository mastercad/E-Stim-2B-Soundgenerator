"""
Auto-Generator Screen - Automatic session generation with parameter controls.

Allows users to:
- Set overall session parameters (duration, style, intensity curve)
- Configure frequency and waveform preferences
- Generate sessions automatically
- Preview and save generated sessions
"""

from kivy.metrics import dp

from kivy.uix.scrollview import ScrollView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from ui.widgets.card_container import CardBox
from kivymd.uix.slider import MDSlider
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.chip import MDChip

from core.waveforms import WaveformType
from core.session_generator import (
    SessionGenerator, GeneratorConfig, SessionStyle, IntensityCurve
)
from core.session import SessionLibrary


class AutoGeneratorScreen(MDScreen):
    """Screen for automatic session generation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "auto_generator"
        self._config = GeneratorConfig()
        self._generator = SessionGenerator()
        self._library = SessionLibrary("sessions")
        self._last_session = None
        self._built = False

    def _open_nav(self):
        from kivymd.app import MDApp
        MDApp.get_running_app().nav_drawer.set_state("toggle")

    def on_enter(self):
        if not self._built:
            self._build_ui()
            self._built = True

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        # Toolbar
        toolbar = MDBoxLayout(
            size_hint_y=None, height=dp(56),
            md_bg_color=[0.12, 0.12, 0.15, 1],
            padding=[dp(8), 0],
        )
        back_btn = MDFlatButton(
            text="←", font_size="24sp",
            on_release=lambda x: setattr(self.manager, 'current', 'home'),
            theme_text_color="Custom", text_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(back_btn)
        toolbar.add_widget(MDLabel(
            text="Auto-Generator", font_style="H6", halign="center",
        ))
        menu_btn = MDIconButton(
            icon="menu",
            on_release=lambda x: self._open_nav(),
            theme_icon_color="Custom",
            icon_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(menu_btn)
        root.add_widget(toolbar)

        # Scrollable content
        scroll = ScrollView(do_scroll_x=False)
        content = MDBoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(12),
            size_hint_y=None,
            adaptive_height=True,
        )

        # ─── Session Style ────────────────────────────────
        style_card = self._build_section("Session-Stil")

        style_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        style_box.add_widget(MDLabel(text="Stil", size_hint_x=0.3))
        self._style_btn = MDRaisedButton(
            text="Rhythmisch",
            size_hint_x=0.7,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        style_items = [
            {"text": s.value.capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=s: self._set_style(x)}
            for s in SessionStyle
        ]
        self._style_menu = MDDropdownMenu(caller=self._style_btn, items=style_items, width_mult=3)
        self._style_btn.bind(on_release=lambda x: self._style_menu.open())
        style_box.add_widget(self._style_btn)
        style_card.add_widget(style_box)

        # Intensity curve
        curve_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        curve_box.add_widget(MDLabel(text="Intensitätskurve", size_hint_x=0.3))
        self._curve_btn = MDRaisedButton(
            text="Plateau",
            size_hint_x=0.7,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        curve_items = [
            {"text": c.value.replace("_", " ").capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=c: self._set_curve(x)}
            for c in IntensityCurve
        ]
        self._curve_menu = MDDropdownMenu(caller=self._curve_btn, items=curve_items, width_mult=4)
        self._curve_btn.bind(on_release=lambda x: self._curve_menu.open())
        curve_box.add_widget(self._curve_btn)
        style_card.add_widget(curve_box)

        content.add_widget(style_card)

        # ─── Duration & Intensity ─────────────────────────
        params_card = self._build_section("Parameter")

        # Duration
        dur_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        dur_box.add_widget(MDLabel(text="Dauer", size_hint_x=0.2))
        self._dur_slider = MDSlider(min=1, max=120, value=5, size_hint_x=0.6)
        self._dur_label = MDLabel(text="5 Min", size_hint_x=0.2, halign="right", font_style="Caption")
        self._dur_slider.bind(value=self._on_dur_change)
        dur_box.add_widget(self._dur_slider)
        dur_box.add_widget(self._dur_label)
        params_card.add_widget(dur_box)

        # Min intensity
        min_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        min_box.add_widget(MDLabel(text="Min. Intensität", size_hint_x=0.3))
        self._min_slider = MDSlider(min=0, max=100, value=20, size_hint_x=0.5)
        self._min_label = MDLabel(text="20%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._min_slider.bind(value=lambda i, v: self._on_intensity_change('min', v))
        min_box.add_widget(self._min_slider)
        min_box.add_widget(self._min_label)
        params_card.add_widget(min_box)

        # Max intensity
        max_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        max_box.add_widget(MDLabel(text="Max. Intensität", size_hint_x=0.3))
        self._max_slider = MDSlider(min=0, max=100, value=90, size_hint_x=0.5)
        self._max_label = MDLabel(text="90%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._max_slider.bind(value=lambda i, v: self._on_intensity_change('max', v))
        max_box.add_widget(self._max_slider)
        max_box.add_widget(self._max_label)
        params_card.add_widget(max_box)

        # Randomness
        rand_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        rand_box.add_widget(MDLabel(text="Zufälligkeit", size_hint_x=0.2))
        self._rand_slider = MDSlider(min=0, max=100, value=30, size_hint_x=0.6)
        self._rand_label = MDLabel(text="30%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._rand_slider.bind(value=self._on_rand_change)
        rand_box.add_widget(self._rand_slider)
        rand_box.add_widget(self._rand_label)
        params_card.add_widget(rand_box)

        # Channel symmetry
        sym_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        sym_box.add_widget(MDLabel(text="Kanal-Symmetrie", size_hint_x=0.3))
        self._sym_slider = MDSlider(min=0, max=100, value=70, size_hint_x=0.5)
        self._sym_label = MDLabel(text="70%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._sym_slider.bind(value=self._on_sym_change)
        sym_box.add_widget(self._sym_slider)
        sym_box.add_widget(self._sym_label)
        params_card.add_widget(sym_box)

        content.add_widget(params_card)

        # ─── Frequency Range ─────────────────────────────
        freq_card = self._build_section("Frequenz-Bereich")

        fmin_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        fmin_box.add_widget(MDLabel(text="Min Hz", size_hint_x=0.2))
        self._fmin_slider = MDSlider(min=2, max=150, value=10, size_hint_x=0.6)
        self._fmin_label = MDLabel(text="10 Hz", size_hint_x=0.2, halign="right", font_style="Caption")
        self._fmin_slider.bind(value=lambda i, v: self._on_freq_range('min', v))
        fmin_box.add_widget(self._fmin_slider)
        fmin_box.add_widget(self._fmin_label)
        freq_card.add_widget(fmin_box)

        fmax_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        fmax_box.add_widget(MDLabel(text="Max Hz", size_hint_x=0.2))
        self._fmax_slider = MDSlider(min=50, max=1000, value=250, size_hint_x=0.6)
        self._fmax_label = MDLabel(text="250 Hz", size_hint_x=0.2, halign="right", font_style="Caption")
        self._fmax_slider.bind(value=lambda i, v: self._on_freq_range('max', v))
        fmax_box.add_widget(self._fmax_slider)
        fmax_box.add_widget(self._fmax_label)
        freq_card.add_widget(fmax_box)

        content.add_widget(freq_card)

        # ─── Generate Button ─────────────────────────────
        gen_box = MDBoxLayout(
            size_hint_y=None, height=dp(60),
            spacing=dp(12),
            padding=[0, dp(8)],
        )
        self._gen_btn = MDRaisedButton(
            text="🎲 Session generieren",
            md_bg_color=[0.3, 0.6, 0.3, 1],
            font_size=dp(16),
            size_hint_x=0.5,
            on_release=self._generate,
        )
        gen_box.add_widget(self._gen_btn)

        self._save_btn = MDRaisedButton(
            text="💾 Speichern",
            md_bg_color=[0.2, 0.4, 0.8, 1],
            font_size=dp(16),
            size_hint_x=0.25,
            on_release=self._save,
            disabled=True,
        )
        gen_box.add_widget(self._save_btn)

        self._play_btn = MDRaisedButton(
            text="▶ Abspielen",
            md_bg_color=[0.5, 0.3, 0.6, 1],
            font_size=dp(16),
            size_hint_x=0.25,
            on_release=self._play,
            disabled=True,
        )
        gen_box.add_widget(self._play_btn)

        content.add_widget(gen_box)

        # ─── Result Info ─────────────────────────────────
        self._result_card = CardBox(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(200),
            md_bg_color=[0.12, 0.15, 0.12, 1],
            radius=[dp(8)],
        )
        self._result_label = MDLabel(
            text="Noch keine Session generiert.\n\nKonfiguriere die Parameter oben und drücke 'Session generieren'.",
            font_style="Body2",
            theme_text_color="Custom",
            text_color=[0.6, 0.6, 0.6, 1],
        )
        self._result_card.add_widget(self._result_label)
        content.add_widget(self._result_card)

        # Spacer
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(50)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _build_section(self, title: str) -> CardBox:
        """Build a section card with title."""
        card = CardBox(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(6),
            size_hint_y=None,
            md_bg_color=[0.15, 0.15, 0.18, 1],
            radius=[dp(8)],
        )
        card.bind(minimum_height=card.setter('height'))
        card.add_widget(MDLabel(
            text=title,
            font_style="Subtitle1",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=[0.3, 0.7, 1.0, 1],
        ))
        return card

    # ─── Event Handlers ──────────────────────────────────

    def _set_style(self, style):
        self._config.style = style
        self._style_btn.text = style.value.capitalize()
        self._style_menu.dismiss()

    def _set_curve(self, curve):
        self._config.intensity_curve = curve
        self._curve_btn.text = curve.value.replace("_", " ").capitalize()
        self._curve_menu.dismiss()

    def _on_dur_change(self, instance, value):
        self._config.total_duration = value * 60
        hours = int(value) // 60
        mins = int(value) % 60
        if hours > 0:
            self._dur_label.text = f"{hours}h {mins:02d}m" if mins else f"{hours}h"
        else:
            self._dur_label.text = f"{int(value)} Min"

    def _on_intensity_change(self, which, value):
        if which == 'min':
            self._config.min_intensity = value / 100.0
            self._min_label.text = f"{int(value)}%"
        else:
            self._config.max_intensity = value / 100.0
            self._max_label.text = f"{int(value)}%"

    def _on_rand_change(self, instance, value):
        self._config.randomness = value / 100.0
        self._rand_label.text = f"{int(value)}%"

    def _on_sym_change(self, instance, value):
        self._config.channel_symmetry = value / 100.0
        self._sym_label.text = f"{int(value)}%"

    def _on_freq_range(self, which, value):
        if which == 'min':
            self._config.freq_range = (value, self._config.freq_range[1])
            self._fmin_label.text = f"{int(value)} Hz"
        else:
            self._config.freq_range = (self._config.freq_range[0], value)
            self._fmax_label.text = f"{int(value)} Hz"

    def _generate(self, *args):
        """Generate a new session."""
        self._config.session_name = f"Auto: {self._config.style.value.capitalize()}"

        self._last_session = self._generator.generate(self._config)

        # Display result summary (limit to avoid giant black card on phones)
        session = self._last_session
        total_segs = len(session.segments)
        max_show = 15  # Show at most this many segments

        info_lines = [
            f"[b]{session.name}[/b]",
            f"Dauer: {session.total_duration_formatted}",
            f"Segmente: {total_segs}",
            "",
        ]

        for i, seg in enumerate(session.segments[:max_show]):
            info_lines.append(
                f"  {i + 1}. {seg.name} ({seg.duration:.0f}s) - "
                f"A:{seg.channel_a.waveform.value}@{seg.channel_a.frequency:.0f}Hz "
                f"B:{seg.channel_b.waveform.value}@{seg.channel_b.frequency:.0f}Hz"
            )

        if total_segs > max_show:
            info_lines.append(f"  ... und {total_segs - max_show} weitere Segmente")

        self._result_label.text = "\n".join(info_lines)
        self._result_label.markup = True

        # Cap card height to a sensible maximum
        shown = min(total_segs, max_show) + (1 if total_segs > max_show else 0)
        self._result_card.height = min(dp(50 + shown * 22), dp(420))

        self._save_btn.disabled = False
        self._play_btn.disabled = False

    def _save(self, *args):
        """Save the generated session."""
        if self._last_session:
            filepath = self._library.save_session(self._last_session)
            print(f"Session gespeichert: {filepath}")

    def _play(self, *args):
        """Switch to player and play the generated session."""
        if self._last_session:
            # Navigate to player screen with the session
            player = self.manager.get_screen("player")
            player.load_and_play(self._last_session)
            self.manager.current = "player"
