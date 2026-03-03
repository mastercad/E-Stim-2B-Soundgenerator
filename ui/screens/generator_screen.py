"""
Generator Screen - Manual waveform creation with real-time preview.

Allows users to:
- Select waveform type for each channel
- Adjust frequency, amplitude, duty cycle
- Add modulation effects
- Preview and export the sound
"""

from kivy.clock import Clock
from kivy.metrics import dp

from kivy.uix.scrollview import ScrollView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from ui.widgets.card_container import CardBox
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.slider import MDSlider
from kivymd.uix.menu import MDDropdownMenu

import numpy as np
import os

from core.waveforms import WaveformType, StereoWaveformGenerator
from core.modulation import Modulator, ModulationParams, ModulationType
from core.audio_engine import AudioEngine
from core.export import AudioExporter
from ui.widgets.waveform_display import WaveformDisplay


class GeneratorScreen(MDScreen):
    """Screen for manually creating waveforms."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "generator"
        self._engine = None
        self._generator = StereoWaveformGenerator(44100)
        self._exporter = AudioExporter(44100)
        self._preview_event = None
        self._preview_pending = None  # Throttled preview update
        self._built = False

        # Current settings
        self._settings = {
            'waveform_a': WaveformType.SINE,
            'waveform_b': WaveformType.SINE,
            'frequency_a': 80.0,
            'frequency_b': 80.0,
            'amplitude_a': 0.7,
            'amplitude_b': 0.7,
            'duty_cycle_a': 0.5,
            'duty_cycle_b': 0.5,
            'mod_type_a': ModulationType.NONE,
            'mod_type_b': ModulationType.NONE,
            'mod_rate_a': 1.0,
            'mod_rate_b': 1.0,
            'mod_depth_a': 0.5,
            'mod_depth_b': 0.5,
            'link_channels': True,
            'duration': 10.0,
        }

    def _open_nav(self):
        from kivymd.app import MDApp
        MDApp.get_running_app().nav_drawer.set_state("toggle")

    def on_enter(self):
        if not self._built:
            self._build_ui()
            self._built = True
        self._update_preview()

    def on_leave(self):
        if self._engine and self._engine.is_playing:
            self._engine.stop()

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        # Toolbar
        toolbar = MDBoxLayout(
            size_hint_y=None, height=dp(56),
            md_bg_color=[0.12, 0.12, 0.15, 1],
            padding=[dp(8), 0],
        )
        back_btn = MDFlatButton(
            text="←",
            font_size="24sp",
            on_release=lambda x: setattr(self.manager, 'current', 'home'),
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(back_btn)
        toolbar.add_widget(MDLabel(
            text="Wellenform Generator",
            font_style="H6",
            halign="center",
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

        # Waveform Preview
        preview_card = CardBox(
            orientation="vertical",
            padding=dp(8),
            size_hint_y=None,
            height=dp(180),
            md_bg_color=[0.12, 0.12, 0.15, 1],
            radius=[dp(8)],
        )
        preview_card.add_widget(MDLabel(
            text="Vorschau",
            font_style="Caption",
            size_hint_y=None,
            height=dp(20),
        ))
        self._waveform_display = WaveformDisplay(
            size_hint_y=None,
            height=dp(140),
        )
        preview_card.add_widget(self._waveform_display)
        content.add_widget(preview_card)

        # Link channels toggle
        link_box = MDBoxLayout(
            size_hint_y=None, height=dp(40),
            spacing=dp(8),
        )
        link_box.add_widget(MDLabel(
            text="Kanäle verknüpfen",
            font_style="Body2",
        ))
        from kivy.clock import Clock
        self._link_switch = MDSwitch()
        link_box.add_widget(self._link_switch)
        # Set active after widget is fully built (avoids ids.thumb crash)
        Clock.schedule_once(lambda dt: setattr(self._link_switch, 'active', True), 0)
        self._link_switch.bind(active=self._on_link_toggle)
        content.add_widget(link_box)

        # Channel A controls
        content.add_widget(self._build_channel_card("A", "a"))

        # Channel B controls
        self._channel_b_card = self._build_channel_card("B", "b")
        self._channel_b_card.disabled = True
        self._channel_b_card.opacity = 0.5
        content.add_widget(self._channel_b_card)

        # Duration control
        dur_card = CardBox(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(80),
            md_bg_color=[0.15, 0.15, 0.18, 1],
            radius=[dp(8)],
        )
        dur_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        dur_box.add_widget(MDLabel(text="Dauer", size_hint_x=0.2, font_style="Body2"))
        self._dur_slider = MDSlider(min=1, max=1800, value=10, size_hint_x=0.6)
        self._dur_slider.bind(value=self._on_duration_change)
        dur_box.add_widget(self._dur_slider)
        self._dur_label = MDLabel(text="10 Sek", size_hint_x=0.2, font_style="Caption", halign="right")
        dur_box.add_widget(self._dur_label)
        dur_card.add_widget(dur_box)
        content.add_widget(dur_card)

        # Action buttons
        actions = MDBoxLayout(
            size_hint_y=None, height=dp(50),
            spacing=dp(12),
        )
        self._play_btn = MDRaisedButton(
            text="▶ Abspielen",
            md_bg_color=[0.2, 0.6, 0.2, 1],
            on_release=self._toggle_play,
        )
        actions.add_widget(self._play_btn)

        export_btn = MDRaisedButton(
            text="💾 Als WAV speichern",
            md_bg_color=[0.2, 0.4, 0.8, 1],
            on_release=self._export_wav,
        )
        actions.add_widget(export_btn)
        content.add_widget(actions)

        # Spacer
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(50)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _build_channel_card(self, label: str, channel_id: str) -> CardBox:
        """Build a channel control card."""
        color = [0.2, 0.5, 1.0, 1.0] if channel_id == "a" else [1.0, 0.3, 0.3, 1.0]

        card = CardBox(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(6),
            size_hint_y=None,
            height=dp(340),
            md_bg_color=[0.15, 0.15, 0.18, 1],
            radius=[dp(8)],
        )

        # Header
        card.add_widget(MDLabel(
            text=f"Kanal {label} ({'Links → E-Stim A' if channel_id == 'a' else 'Rechts → E-Stim B'})",
            font_style="Subtitle1",
            theme_text_color="Custom",
            text_color=color,
            size_hint_y=None,
            height=dp(30),
        ))

        # Waveform selector
        wf_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        wf_box.add_widget(MDLabel(text="Wellenform", size_hint_x=0.3, font_style="Body2"))
        wf_btn = MDRaisedButton(
            text="Sinus",
            size_hint_x=0.7,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        wf_items = [
            {"text": wf.value.capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=wf, b=wf_btn, c=channel_id: self._set_waveform(x, b, c)}
            for wf in WaveformType if wf not in [WaveformType.CHIRP, WaveformType.BURST]
        ]
        wf_menu = MDDropdownMenu(caller=wf_btn, items=wf_items, width_mult=3)
        wf_btn.bind(on_release=lambda x: wf_menu.open())
        setattr(self, f'_wf_btn_{channel_id}', wf_btn)
        wf_box.add_widget(wf_btn)
        card.add_widget(wf_box)

        # Frequency
        freq_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        freq_box.add_widget(MDLabel(text="Frequenz", size_hint_x=0.2, font_style="Body2"))
        freq_slider = MDSlider(min=1, max=1000, value=80, size_hint_x=0.6)
        freq_label = MDLabel(text="80 Hz", size_hint_x=0.2, font_style="Caption", halign="right")
        freq_slider.bind(value=lambda inst, val, c=channel_id, l=freq_label: self._on_freq_change(c, val, l))
        freq_box.add_widget(freq_slider)
        freq_box.add_widget(freq_label)
        setattr(self, f'_freq_slider_{channel_id}', freq_slider)
        setattr(self, f'_freq_label_{channel_id}', freq_label)
        card.add_widget(freq_box)

        # Amplitude
        amp_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        amp_box.add_widget(MDLabel(text="Amplitude", size_hint_x=0.2, font_style="Body2"))
        amp_slider = MDSlider(min=0, max=100, value=70, size_hint_x=0.6)
        amp_label = MDLabel(text="70%", size_hint_x=0.2, font_style="Caption", halign="right")
        amp_slider.bind(value=lambda inst, val, c=channel_id, l=amp_label: self._on_amp_change(c, val, l))
        amp_box.add_widget(amp_slider)
        amp_box.add_widget(amp_label)
        setattr(self, f'_amp_slider_{channel_id}', amp_slider)
        setattr(self, f'_amp_label_{channel_id}', amp_label)
        card.add_widget(amp_box)

        # Modulation
        card.add_widget(MDLabel(
            text="Modulation",
            font_style="Caption",
            size_hint_y=None,
            height=dp(20),
            theme_text_color="Custom",
            text_color=[0.6, 0.6, 0.6, 1],
        ))

        # Mod type selector
        mod_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mod_box.add_widget(MDLabel(text="Typ", size_hint_x=0.3, font_style="Body2"))
        mod_btn = MDRaisedButton(
            text="Keine",
            size_hint_x=0.7,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        mod_items = [
            {"text": mt.value.upper() if mt.value != "none" else "Keine",
             "viewclass": "OneLineListItem",
             "on_release": lambda x=mt, b=mod_btn, c=channel_id: self._set_modulation(x, b, c)}
            for mt in ModulationType
        ]
        mod_menu = MDDropdownMenu(caller=mod_btn, items=mod_items, width_mult=3)
        mod_btn.bind(on_release=lambda x: mod_menu.open())
        setattr(self, f'_mod_btn_{channel_id}', mod_btn)
        mod_box.add_widget(mod_btn)
        card.add_widget(mod_box)

        # Mod rate
        mrate_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mrate_box.add_widget(MDLabel(text="Rate", size_hint_x=0.2, font_style="Caption"))
        mrate_slider = MDSlider(min=1, max=100, value=10, size_hint_x=0.6)
        mrate_label = MDLabel(text="1.0 Hz", size_hint_x=0.2, font_style="Caption", halign="right")
        mrate_slider.bind(value=lambda inst, val, c=channel_id, l=mrate_label: self._on_mod_rate_change(c, val, l))
        mrate_box.add_widget(mrate_slider)
        mrate_box.add_widget(mrate_label)
        setattr(self, f'_mrate_slider_{channel_id}', mrate_slider)
        card.add_widget(mrate_box)

        # Mod depth
        mdepth_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mdepth_box.add_widget(MDLabel(text="Tiefe", size_hint_x=0.2, font_style="Caption"))
        mdepth_slider = MDSlider(min=0, max=100, value=50, size_hint_x=0.6)
        mdepth_label = MDLabel(text="50%", size_hint_x=0.2, font_style="Caption", halign="right")
        mdepth_slider.bind(value=lambda inst, val, c=channel_id, l=mdepth_label: self._on_mod_depth_change(c, val, l))
        mdepth_box.add_widget(mdepth_slider)
        mdepth_box.add_widget(mdepth_label)
        setattr(self, f'_mdepth_slider_{channel_id}', mdepth_slider)
        card.add_widget(mdepth_box)

        return card

    # ─── Event Handlers ─────────────────────────────────────────────

    def _on_link_toggle(self, instance, value):
        self._settings['link_channels'] = value
        self._channel_b_card.disabled = value
        self._channel_b_card.opacity = 0.5 if value else 1.0

        if value:
            # Linking: sync B to A values (both settings and slider widgets)
            self._sync_channel_b_to_a()
        else:
            # Unlinking: update B sliders to show current B settings
            self._sync_b_sliders_to_settings()

        self._schedule_preview()

    def _sync_channel_b_to_a(self):
        """Copy all Channel A settings to Channel B and update B slider widgets."""
        s = self._settings
        s['waveform_b'] = s['waveform_a']
        s['frequency_b'] = s['frequency_a']
        s['amplitude_b'] = s['amplitude_a']
        s['mod_type_b'] = s['mod_type_a']
        s['mod_rate_b'] = s['mod_rate_a']
        s['mod_depth_b'] = s['mod_depth_a']
        self._sync_b_sliders_to_settings()

    def _sync_b_sliders_to_settings(self):
        """Update Channel B slider widgets to match the current B settings."""
        s = self._settings
        self._freq_slider_b.value = s['frequency_b']
        self._freq_label_b.text = f"{int(s['frequency_b'])} Hz"
        self._amp_slider_b.value = s['amplitude_b'] * 100
        self._amp_label_b.text = f"{int(s['amplitude_b'] * 100)}%"
        self._mrate_slider_b.value = s['mod_rate_b'] * 10
        self._mdepth_slider_b.value = s['mod_depth_b'] * 100
        if hasattr(self, '_wf_btn_b'):
            self._wf_btn_b.text = s['waveform_b'].value.capitalize()
        if hasattr(self, '_mod_btn_b'):
            mt = s['mod_type_b']
            self._mod_btn_b.text = mt.value.upper() if mt.value != "none" else "Keine"

    def _set_waveform(self, waveform, button, channel):
        button.text = waveform.value.capitalize()
        self._settings[f'waveform_{channel}'] = waveform
        if self._settings['link_channels'] and channel == 'a':
            self._settings['waveform_b'] = waveform
        self._schedule_preview()
        # Update live engine
        if self._engine and self._engine.is_playing:
            self._engine.set_waveform(channel, waveform)
            if self._settings['link_channels']:
                self._engine.set_waveform('b', waveform)

    def _on_freq_change(self, channel, value, label):
        label.text = f"{int(value)} Hz"
        self._settings[f'frequency_{channel}'] = value
        if self._settings['link_channels'] and channel == 'a':
            self._settings['frequency_b'] = value
        self._schedule_preview()  # throttled
        if self._engine and self._engine.is_playing:
            self._engine.set_frequency(channel, value)
            if self._settings['link_channels']:
                self._engine.set_frequency('b', value)

    def _on_amp_change(self, channel, value, label):
        label.text = f"{int(value)}%"
        self._settings[f'amplitude_{channel}'] = value / 100.0
        if self._settings['link_channels'] and channel == 'a':
            self._settings['amplitude_b'] = value / 100.0
        self._schedule_preview()  # throttled
        if self._engine and self._engine.is_playing:
            self._engine.set_amplitude(channel, value / 100.0)
            if self._settings['link_channels']:
                self._engine.set_amplitude('b', value / 100.0)

    def _set_modulation(self, mod_type, button, channel):
        button.text = mod_type.value.upper() if mod_type.value != "none" else "Keine"
        self._settings[f'mod_type_{channel}'] = mod_type
        if self._settings['link_channels'] and channel == 'a':
            self._settings['mod_type_b'] = mod_type
        self._schedule_preview()

    def _on_mod_rate_change(self, channel, value, label):
        rate = value / 10.0
        label.text = f"{rate:.1f} Hz"
        self._settings[f'mod_rate_{channel}'] = rate
        if self._settings['link_channels'] and channel == 'a':
            self._settings['mod_rate_b'] = rate

    def _on_mod_depth_change(self, channel, value, label):
        label.text = f"{int(value)}%"
        self._settings[f'mod_depth_{channel}'] = value / 100.0
        if self._settings['link_channels'] and channel == 'a':
            self._settings['mod_depth_b'] = value / 100.0

    def _on_duration_change(self, instance, value):
        self._settings['duration'] = value
        if value >= 60:
            mins = int(value) // 60
            secs = int(value) % 60
            self._dur_label.text = f"{mins}:{secs:02d} Min" if secs else f"{mins} Min"
        else:
            self._dur_label.text = f"{int(value)} Sek"

    def _schedule_preview(self):
        """Schedule a throttled preview update (~8 FPS max during slider drag)."""
        if self._preview_pending is not None:
            self._preview_pending.cancel()
        self._preview_pending = Clock.schedule_once(lambda dt: self._update_preview(), 0.12)

    def _update_preview(self):
        """Update the waveform preview display."""
        self._preview_pending = None
        try:
            s = self._settings
            preview_samples = 500  # fewer samples – only used for visual display
            stereo = self._generator.generate_stereo(
                waveform_a=s['waveform_a'],
                frequency_a=s['frequency_a'],
                amplitude_a=s['amplitude_a'],
                duty_cycle_a=s['duty_cycle_a'],
                waveform_b=s['waveform_b'] if not s['link_channels'] else s['waveform_a'],
                frequency_b=s['frequency_b'] if not s['link_channels'] else s['frequency_a'],
                amplitude_b=s['amplitude_b'] if not s['link_channels'] else s['amplitude_a'],
                num_samples=preview_samples,
            )
            self._waveform_display.set_data(stereo[:, 0], stereo[:, 1])
        except Exception as e:
            print(f"Preview-Fehler: {e}")

    def _toggle_play(self, *args):
        """Toggle audio playback."""
        if self._engine and self._engine.is_playing:
            self._engine.stop()
            self._play_btn.text = "▶ Abspielen"
            self._play_btn.md_bg_color = [0.2, 0.6, 0.2, 1]
            return

        try:
            if not self._engine:
                self._engine = AudioEngine()

            s = self._settings
            self._engine.live_params.update(
                waveform_a=s['waveform_a'],
                frequency_a=s['frequency_a'],
                amplitude_a=s['amplitude_a'],
                duty_cycle_a=s['duty_cycle_a'],
                waveform_b=s['waveform_b'] if not s['link_channels'] else s['waveform_a'],
                frequency_b=s['frequency_b'] if not s['link_channels'] else s['frequency_a'],
                amplitude_b=s['amplitude_b'] if not s['link_channels'] else s['amplitude_a'],
                mod_type_a=s['mod_type_a'],
                mod_rate_a=s['mod_rate_a'],
                mod_depth_a=s['mod_depth_a'],
                mod_type_b=s['mod_type_b'] if not s['link_channels'] else s['mod_type_a'],
                mod_rate_b=s['mod_rate_b'] if not s['link_channels'] else s['mod_rate_a'],
                mod_depth_b=s['mod_depth_b'] if not s['link_channels'] else s['mod_depth_a'],
            )
            self._engine.play_free()
            self._play_btn.text = "⏹ Stoppen"
            self._play_btn.md_bg_color = [0.8, 0.2, 0.2, 1]
        except Exception as e:
            print(f"Wiedergabe-Fehler: {e}")

    def _export_wav(self, *args):
        """Export current settings as WAV file."""
        from core.patterns import PatternSegment, ChannelConfig
        from core.modulation import ModulationParams

        s = self._settings
        segment = PatternSegment(
            name="Generator Export",
            duration=s['duration'],
            channel_a=ChannelConfig(
                waveform=s['waveform_a'],
                frequency=s['frequency_a'],
                amplitude=s['amplitude_a'],
                duty_cycle=s['duty_cycle_a'],
            ),
            channel_b=ChannelConfig(
                waveform=s['waveform_b'] if not s['link_channels'] else s['waveform_a'],
                frequency=s['frequency_b'] if not s['link_channels'] else s['frequency_a'],
                amplitude=s['amplitude_b'] if not s['link_channels'] else s['amplitude_a'],
            ),
            modulation_a=ModulationParams(
                mod_type=s['mod_type_a'],
                rate=s['mod_rate_a'],
                depth=s['mod_depth_a'],
            ),
            modulation_b=ModulationParams(
                mod_type=s['mod_type_b'] if not s['link_channels'] else s['mod_type_a'],
                rate=s['mod_rate_b'] if not s['link_channels'] else s['mod_rate_a'],
                depth=s['mod_depth_b'] if not s['link_channels'] else s['mod_depth_a'],
            ),
        )

        filepath = os.path.join("sessions", f"generator_export_{segment.id}.wav")
        try:
            self._exporter.export_segment(segment, filepath)
            print(f"Exportiert nach: {filepath}")
        except Exception as e:
            print(f"Export-Fehler: {e}")
