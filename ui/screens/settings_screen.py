"""
Settings Screen - Application configuration.
"""

from kivy.metrics import dp

from ui.widgets.slider_scrollview import SliderFriendlyScrollView as ScrollView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.slider import MDSlider
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.menu import MDDropdownMenu


class SettingsScreen(MDScreen):
    """Application settings screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "settings"
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
            text="Einstellungen", font_style="H6", halign="center",
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
        scroll = ScrollView()
        content = MDBoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(12),
            size_hint_y=None,
            adaptive_height=True,
        )

        # ─── Audio Settings ──────────────────────────────
        audio_card = self._build_section("Audio")

        # Sample rate
        sr_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        sr_box.add_widget(MDLabel(text="Sample Rate", size_hint_x=0.4))
        sr_btn = MDFlatButton(text="44100 Hz", size_hint_x=0.6)
        sr_box.add_widget(sr_btn)
        audio_card.add_widget(sr_box)

        # Buffer size
        buf_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        buf_box.add_widget(MDLabel(text="Buffer-Größe", size_hint_x=0.3))
        buf_slider = MDSlider(min=256, max=4096, value=1024, size_hint_x=0.5)
        buf_label = MDLabel(text="1024", size_hint_x=0.2, halign="right", font_style="Caption")
        buf_slider.bind(value=lambda i, v: setattr(buf_label, 'text', str(int(v))))
        buf_box.add_widget(buf_slider)
        buf_box.add_widget(buf_label)
        audio_card.add_widget(buf_box)

        audio_card.add_widget(MDLabel(
            text="Kleinerer Buffer = schnellere Reaktion, aber mehr CPU.\n"
                 "Empfohlen: 1024 für Desktop, 2048 für Android.",
            font_style="Caption",
            size_hint_y=None,
            height=dp(40),
            theme_text_color="Custom",
            text_color=[0.4, 0.4, 0.4, 1],
        ))

        content.add_widget(audio_card)

        # ─── Safety Settings ─────────────────────────────
        safety_card = self._build_section("Sicherheit")

        # Max amplitude
        max_amp_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        max_amp_box.add_widget(MDLabel(text="Max. Amplitude", size_hint_x=0.3))
        max_amp_slider = MDSlider(min=10, max=100, value=90, size_hint_x=0.5)
        max_amp_label = MDLabel(text="90%", size_hint_x=0.2, halign="right", font_style="Caption")
        max_amp_slider.bind(value=lambda i, v: setattr(max_amp_label, 'text', f"{int(v)}%"))
        max_amp_box.add_widget(max_amp_slider)
        max_amp_box.add_widget(max_amp_label)
        safety_card.add_widget(max_amp_box)

        # Soft start
        from kivy.clock import Clock
        soft_start_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        soft_start_box.add_widget(MDLabel(text="Sanfter Start (Fade-In)", size_hint_x=0.6))
        soft_start_switch = MDSwitch()
        soft_start_box.add_widget(soft_start_switch)
        Clock.schedule_once(lambda dt: setattr(soft_start_switch, 'active', True), 0)
        safety_card.add_widget(soft_start_box)

        safety_card.add_widget(MDLabel(
            text="⚠ Beginne immer mit niedriger Intensität!\n"
                 "Erhöhe die Amplitude schrittweise am E-Stim 2B Gerät.",
            font_style="Caption",
            size_hint_y=None,
            height=dp(40),
            theme_text_color="Custom",
            text_color=[1.0, 0.7, 0.3, 1],
        ))

        content.add_widget(safety_card)

        # ─── Export Settings ─────────────────────────────
        export_card = self._build_section("Export")

        bit_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        bit_box.add_widget(MDLabel(text="WAV Format", size_hint_x=0.4))
        bit_box.add_widget(MDLabel(text="16-bit PCM", size_hint_x=0.6, halign="right"))
        export_card.add_widget(bit_box)

        dir_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        dir_box.add_widget(MDLabel(text="Speicherort", size_hint_x=0.3))
        dir_box.add_widget(MDLabel(
            text="./sessions/",
            size_hint_x=0.7, halign="right",
            font_style="Caption",
        ))
        export_card.add_widget(dir_box)

        content.add_widget(export_card)

        # ─── About ───────────────────────────────────────
        about_card = self._build_section("Info")
        about_card.add_widget(MDLabel(
            text="E-Stim 2B Sound Generator v1.0.0\n\n"
                 "Erstellt individuelle Audio-Stimulationsmuster\n"
                 "für das E-Stim 2B Elektrostimulationsgerät.\n\n"
                 "Linker Kanal → E-Stim Kanal A\n"
                 "Rechter Kanal → E-Stim Kanal B",
            font_style="Body2",
            size_hint_y=None,
            height=dp(120),
            theme_text_color="Custom",
            text_color=[0.6, 0.6, 0.6, 1],
        ))
        content.add_widget(about_card)

        # Spacer
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(50)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _build_section(self, title: str) -> MDCard:
        card = MDCard(
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
            height=dp(28),
            theme_text_color="Custom",
            text_color=[0.3, 0.7, 1.0, 1],
        ))
        return card
