"""
Player Screen - Session playback with real-time controls.

The heart of the app: plays sessions and allows real-time modification
of all parameters to shape the stimulation experience live.
"""

from kivy.clock import Clock
from kivy.metrics import dp

from ui.widgets.slider_scrollview import SliderFriendlyScrollView as ScrollView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.slider import MDSlider
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.progressbar import MDProgressBar

import numpy as np

from core.waveforms import WaveformType
from core.modulation import ModulationType
from core.audio_engine import AudioEngine, EngineState
from core.session import Session
from ui.widgets.waveform_display import WaveformDisplay


class PlayerScreen(MDScreen):
    """Session player with real-time modification controls."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "player"
        self._engine = AudioEngine()
        self._session = None
        self._update_event = None
        self._built = False

        # Set up engine callbacks
        self._engine.set_callbacks(
            on_position_update=self._on_position_update,
            on_state_change=self._on_state_change,
            on_segment_change=self._on_segment_change,
        )

    def _open_nav(self):
        from kivymd.app import MDApp
        MDApp.get_running_app().nav_drawer.set_state("toggle")

    def on_enter(self):
        if not self._built:
            self._build_ui()
            self._built = True
        # Start UI update timer
        self._update_event = Clock.schedule_interval(self._update_ui, 1.0 / 15)

    def on_leave(self):
        if self._update_event:
            self._update_event.cancel()
            self._update_event = None

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
            on_release=lambda x: self._go_back(),
            theme_text_color="Custom", text_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(back_btn)
        toolbar.add_widget(MDLabel(
            text="Player", font_style="H6", halign="center",
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
            spacing=dp(10),
            size_hint_y=None,
            adaptive_height=True,
        )

        # ─── Session Info ────────────────────────────────
        self._info_card = MDCard(
            orientation="vertical",
            padding=dp(12),
            size_hint_y=None,
            height=dp(70),
            md_bg_color=[0.12, 0.12, 0.18, 1],
            radius=[dp(8)],
        )
        self._session_name_label = MDLabel(
            text="Keine Session geladen",
            font_style="Subtitle1",
            size_hint_y=None, height=dp(25),
        )
        self._info_card.add_widget(self._session_name_label)
        self._segment_label = MDLabel(
            text="",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.5, 0.5, 1],
            size_hint_y=None, height=dp(20),
        )
        self._info_card.add_widget(self._segment_label)
        content.add_widget(self._info_card)

        # ─── Waveform Display ────────────────────────────
        display_card = MDCard(
            orientation="vertical",
            padding=dp(4),
            size_hint_y=None,
            height=dp(150),
            md_bg_color=[0.1, 0.1, 0.12, 1],
            radius=[dp(8)],
        )
        self._waveform_display = WaveformDisplay(
            size_hint_y=None,
            height=dp(140),
        )
        display_card.add_widget(self._waveform_display)
        content.add_widget(display_card)

        # ─── Transport Controls ──────────────────────────
        transport = MDBoxLayout(
            size_hint_y=None, height=dp(80),
            spacing=dp(8),
        )

        # Progress bar + time
        progress_box = MDBoxLayout(orientation="vertical", size_hint_x=0.6)
        self._progress_bar = MDProgressBar(
            value=0, max=100,
            size_hint_y=None, height=dp(8),
            color=[0.3, 0.7, 1.0, 1],
        )
        progress_box.add_widget(self._progress_bar)

        time_box = MDBoxLayout(size_hint_y=None, height=dp(20))
        self._time_current = MDLabel(
            text="00:00", font_style="Caption", halign="left",
        )
        time_box.add_widget(self._time_current)
        self._time_total = MDLabel(
            text="00:00", font_style="Caption", halign="right",
        )
        time_box.add_widget(self._time_total)
        progress_box.add_widget(time_box)
        transport.add_widget(progress_box)

        # Play/Pause/Stop buttons
        btn_box = MDBoxLayout(size_hint_x=0.4, spacing=dp(4))
        self._play_btn = MDIconButton(
            icon="play",
            on_release=self._toggle_play,
            theme_icon_color="Custom",
            icon_color=[0.3, 0.8, 0.3, 1],
            icon_size=dp(36),
        )
        btn_box.add_widget(self._play_btn)
        self._stop_btn = MDIconButton(
            icon="stop",
            on_release=self._stop,
            theme_icon_color="Custom",
            icon_color=[0.8, 0.3, 0.3, 1],
            icon_size=dp(36),
        )
        btn_box.add_widget(self._stop_btn)
        transport.add_widget(btn_box)

        content.add_widget(transport)

        # ─── Master Controls ─────────────────────────────
        master_card = self._build_section("Master")

        # Volume
        vol_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        vol_box.add_widget(MDLabel(text="🔊 Lautstärke", size_hint_x=0.3))
        self._vol_slider = MDSlider(min=0, max=100, value=80, size_hint_x=0.5)
        self._vol_label = MDLabel(text="80%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._vol_slider.bind(value=self._on_volume_change)
        vol_box.add_widget(self._vol_slider)
        vol_box.add_widget(self._vol_label)
        master_card.add_widget(vol_box)

        # Balance
        bal_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        bal_box.add_widget(MDLabel(text="⚖ Balance A↔B", size_hint_x=0.3))
        self._bal_slider = MDSlider(min=0, max=100, value=50, size_hint_x=0.5)
        self._bal_label = MDLabel(text="Mitte", size_hint_x=0.2, halign="right", font_style="Caption")
        self._bal_slider.bind(value=self._on_balance_change)
        bal_box.add_widget(self._bal_slider)
        bal_box.add_widget(self._bal_label)
        master_card.add_widget(bal_box)

        content.add_widget(master_card)

        # ─── Live Channel A Controls ─────────────────────
        ch_a_card = self._build_section("Kanal A (Links → E-Stim A)")
        ch_a_card.children[0].text_color = [0.3, 0.6, 1.0, 1]  # Blue header

        # Frequency A
        fa_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        fa_box.add_widget(MDLabel(text="Frequenz", size_hint_x=0.25))
        self._freq_a_slider = MDSlider(min=1, max=1000, value=80, size_hint_x=0.55)
        self._freq_a_label = MDLabel(text="80 Hz", size_hint_x=0.2, halign="right", font_style="Caption")
        self._freq_a_slider.bind(value=lambda i, v: self._on_live_freq('a', v))
        fa_box.add_widget(self._freq_a_slider)
        fa_box.add_widget(self._freq_a_label)
        ch_a_card.add_widget(fa_box)

        # Amplitude A
        aa_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        aa_box.add_widget(MDLabel(text="Amplitude", size_hint_x=0.25))
        self._amp_a_slider = MDSlider(min=0, max=100, value=70, size_hint_x=0.55)
        self._amp_a_label = MDLabel(text="70%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._amp_a_slider.bind(value=lambda i, v: self._on_live_amp('a', v))
        aa_box.add_widget(self._amp_a_slider)
        aa_box.add_widget(self._amp_a_label)
        ch_a_card.add_widget(aa_box)

        # Waveform A
        wa_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        wa_box.add_widget(MDLabel(text="Wellenform", size_hint_x=0.3))
        self._wf_a_btn = MDRaisedButton(
            text="Sine", size_hint_x=0.7, md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        wf_items_a = [
            {"text": wf.value.capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=wf: self._on_live_waveform('a', x)}
            for wf in [WaveformType.SINE, WaveformType.SQUARE, WaveformType.TRIANGLE,
                       WaveformType.SAWTOOTH, WaveformType.PULSE]
        ]
        self._wf_a_menu = MDDropdownMenu(caller=self._wf_a_btn, items=wf_items_a, width_mult=3)
        self._wf_a_btn.bind(on_release=lambda x: self._wf_a_menu.open())
        wa_box.add_widget(self._wf_a_btn)
        ch_a_card.add_widget(wa_box)

        # Modulation A
        ma_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        ma_box.add_widget(MDLabel(text="Modulation", size_hint_x=0.3))
        self._mod_a_btn = MDRaisedButton(
            text="Keine", size_hint_x=0.7, md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        mod_items_a = [
            {"text": mt.value.upper() if mt.value != "none" else "Keine",
             "viewclass": "OneLineListItem",
             "on_release": lambda x=mt: self._on_live_mod('a', x)}
            for mt in ModulationType
        ]
        self._mod_a_menu = MDDropdownMenu(caller=self._mod_a_btn, items=mod_items_a, width_mult=3)
        self._mod_a_btn.bind(on_release=lambda x: self._mod_a_menu.open())
        ma_box.add_widget(self._mod_a_btn)
        ch_a_card.add_widget(ma_box)

        # Mod rate A
        mra_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mra_box.add_widget(MDLabel(text="Mod Rate", size_hint_x=0.25, font_style="Caption"))
        self._mrate_a_slider = MDSlider(min=1, max=100, value=10, size_hint_x=0.55)
        self._mrate_a_label = MDLabel(text="1.0 Hz", size_hint_x=0.2, halign="right", font_style="Caption")
        self._mrate_a_slider.bind(value=lambda i, v: self._on_live_mod_rate('a', v))
        mra_box.add_widget(self._mrate_a_slider)
        mra_box.add_widget(self._mrate_a_label)
        ch_a_card.add_widget(mra_box)

        # Mod depth A
        mda_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mda_box.add_widget(MDLabel(text="Mod Tiefe", size_hint_x=0.25, font_style="Caption"))
        self._mdepth_a_slider = MDSlider(min=0, max=100, value=50, size_hint_x=0.55)
        self._mdepth_a_label = MDLabel(text="50%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._mdepth_a_slider.bind(value=lambda i, v: self._on_live_mod_depth('a', v))
        mda_box.add_widget(self._mdepth_a_slider)
        mda_box.add_widget(self._mdepth_a_label)
        ch_a_card.add_widget(mda_box)

        content.add_widget(ch_a_card)

        # ─── Live Channel B Controls ─────────────────────
        ch_b_card = self._build_section("Kanal B (Rechts → E-Stim B)")
        ch_b_card.children[0].text_color = [1.0, 0.4, 0.4, 1]  # Red header

        # Frequency B
        fb_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        fb_box.add_widget(MDLabel(text="Frequenz", size_hint_x=0.25))
        self._freq_b_slider = MDSlider(min=1, max=1000, value=80, size_hint_x=0.55)
        self._freq_b_label = MDLabel(text="80 Hz", size_hint_x=0.2, halign="right", font_style="Caption")
        self._freq_b_slider.bind(value=lambda i, v: self._on_live_freq('b', v))
        fb_box.add_widget(self._freq_b_slider)
        fb_box.add_widget(self._freq_b_label)
        ch_b_card.add_widget(fb_box)

        # Amplitude B
        ab_box = MDBoxLayout(size_hint_y=None, height=dp(50))
        ab_box.add_widget(MDLabel(text="Amplitude", size_hint_x=0.25))
        self._amp_b_slider = MDSlider(min=0, max=100, value=70, size_hint_x=0.55)
        self._amp_b_label = MDLabel(text="70%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._amp_b_slider.bind(value=lambda i, v: self._on_live_amp('b', v))
        ab_box.add_widget(self._amp_b_slider)
        ab_box.add_widget(self._amp_b_label)
        ch_b_card.add_widget(ab_box)

        # Waveform B
        wb_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        wb_box.add_widget(MDLabel(text="Wellenform", size_hint_x=0.3))
        self._wf_b_btn = MDRaisedButton(
            text="Sine", size_hint_x=0.7, md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        wf_items_b = [
            {"text": wf.value.capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=wf: self._on_live_waveform('b', x)}
            for wf in [WaveformType.SINE, WaveformType.SQUARE, WaveformType.TRIANGLE,
                       WaveformType.SAWTOOTH, WaveformType.PULSE]
        ]
        self._wf_b_menu = MDDropdownMenu(caller=self._wf_b_btn, items=wf_items_b, width_mult=3)
        self._wf_b_btn.bind(on_release=lambda x: self._wf_b_menu.open())
        wb_box.add_widget(self._wf_b_btn)
        ch_b_card.add_widget(wb_box)

        # Modulation B
        mb_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mb_box.add_widget(MDLabel(text="Modulation", size_hint_x=0.3))
        self._mod_b_btn = MDRaisedButton(
            text="Keine", size_hint_x=0.7, md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        mod_items_b = [
            {"text": mt.value.upper() if mt.value != "none" else "Keine",
             "viewclass": "OneLineListItem",
             "on_release": lambda x=mt: self._on_live_mod('b', x)}
            for mt in ModulationType
        ]
        self._mod_b_menu = MDDropdownMenu(caller=self._mod_b_btn, items=mod_items_b, width_mult=3)
        self._mod_b_btn.bind(on_release=lambda x: self._mod_b_menu.open())
        mb_box.add_widget(self._mod_b_btn)
        ch_b_card.add_widget(mb_box)

        # Mod rate B
        mrb_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mrb_box.add_widget(MDLabel(text="Mod Rate", size_hint_x=0.25, font_style="Caption"))
        self._mrate_b_slider = MDSlider(min=1, max=100, value=10, size_hint_x=0.55)
        self._mrate_b_label = MDLabel(text="1.0 Hz", size_hint_x=0.2, halign="right", font_style="Caption")
        self._mrate_b_slider.bind(value=lambda i, v: self._on_live_mod_rate('b', v))
        mrb_box.add_widget(self._mrate_b_slider)
        mrb_box.add_widget(self._mrate_b_label)
        ch_b_card.add_widget(mrb_box)

        # Mod depth B
        mdb_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        mdb_box.add_widget(MDLabel(text="Mod Tiefe", size_hint_x=0.25, font_style="Caption"))
        self._mdepth_b_slider = MDSlider(min=0, max=100, value=50, size_hint_x=0.55)
        self._mdepth_b_label = MDLabel(text="50%", size_hint_x=0.2, halign="right", font_style="Caption")
        self._mdepth_b_slider.bind(value=lambda i, v: self._on_live_mod_depth('b', v))
        mdb_box.add_widget(self._mdepth_b_slider)
        mdb_box.add_widget(self._mdepth_b_label)
        ch_b_card.add_widget(mdb_box)

        content.add_widget(ch_b_card)

        # Spacer
        content.add_widget(MDBoxLayout(size_hint_y=None, height=dp(60)))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _build_section(self, title: str) -> MDCard:
        card = MDCard(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(4),
            size_hint_y=None,
            md_bg_color=[0.15, 0.15, 0.18, 1],
            radius=[dp(8)],
        )
        card.bind(minimum_height=card.setter('height'))
        card.add_widget(MDLabel(
            text=title,
            font_style="Subtitle2",
            size_hint_y=None,
            height=dp(24),
            theme_text_color="Custom",
            text_color=[0.3, 0.7, 1.0, 1],
        ))
        return card

    # ─── Transport Controls ──────────────────────────────

    def _toggle_play(self, *args):
        if self._engine.is_playing:
            self._engine.pause()
        elif self._engine.is_paused:
            self._engine.resume()
        elif self._session:
            self._engine.play_session(self._session)
        else:
            # Free play mode
            self._engine.play_free()

    def _stop(self, *args):
        self._engine.stop()
        self._progress_bar.value = 0
        self._time_current.text = "00:00"

    def _go_back(self):
        if self._engine.is_playing:
            self._engine.stop()
        self.manager.current = "home"

    # ─── Live Parameter Controls ─────────────────────────

    def _on_volume_change(self, instance, value):
        self._vol_label.text = f"{int(value)}%"
        self._engine.set_master_volume(value / 100.0)

    def _on_balance_change(self, instance, value):
        balance = (value - 50) / 50.0  # Convert 0-100 to -1.0 to 1.0
        if abs(balance) < 0.05:
            self._bal_label.text = "Mitte"
        elif balance < 0:
            self._bal_label.text = f"A +{int(-balance * 100)}%"
        else:
            self._bal_label.text = f"B +{int(balance * 100)}%"
        self._engine.set_balance(balance)

    def _on_live_freq(self, channel, value):
        label = self._freq_a_label if channel == 'a' else self._freq_b_label
        label.text = f"{int(value)} Hz"
        self._engine.set_frequency(channel, value)

    def _on_live_amp(self, channel, value):
        label = self._amp_a_label if channel == 'a' else self._amp_b_label
        label.text = f"{int(value)}%"
        self._engine.set_amplitude(channel, value / 100.0)

    def _on_live_waveform(self, channel, waveform):
        btn = self._wf_a_btn if channel == 'a' else self._wf_b_btn
        menu = self._wf_a_menu if channel == 'a' else self._wf_b_menu
        btn.text = waveform.value.capitalize()
        menu.dismiss()
        self._engine.set_waveform(channel, waveform)

    def _on_live_mod(self, channel, mod_type):
        btn = self._mod_a_btn if channel == 'a' else self._mod_b_btn
        menu = self._mod_a_menu if channel == 'a' else self._mod_b_menu
        btn.text = mod_type.value.upper() if mod_type.value != "none" else "Keine"
        menu.dismiss()
        self._engine.set_modulation(channel, mod_type)

    def _on_live_mod_rate(self, channel, value):
        rate = value / 10.0
        label = self._mrate_a_label if channel == 'a' else self._mrate_b_label
        label.text = f"{rate:.1f} Hz"
        self._engine.set_modulation(
            channel,
            self._engine.live_params.mod_type_a if channel == 'a' else self._engine.live_params.mod_type_b,
            rate=rate,
        )

    def _on_live_mod_depth(self, channel, value):
        label = self._mdepth_a_label if channel == 'a' else self._mdepth_b_label
        label.text = f"{int(value)}%"
        self._engine.set_modulation(
            channel,
            self._engine.live_params.mod_type_a if channel == 'a' else self._engine.live_params.mod_type_b,
            depth=value / 100.0,
        )

    # ─── Callbacks ──────────────────────────────────────

    def _on_position_update(self, position, segment_idx):
        """Called by engine on position update (from audio thread)."""
        pass  # UI update happens in _update_ui via Clock

    def _on_state_change(self, state):
        """Called by engine on state change."""
        pass  # Handled in _update_ui

    def _on_segment_change(self, index, segment):
        """Called when a new segment starts playing."""
        pass  # Handled in _update_ui

    def _update_ui(self, dt):
        """Periodic UI update (called by Clock)."""
        # Update play button icon
        if self._engine.is_playing:
            self._play_btn.icon = "pause"
        else:
            self._play_btn.icon = "play"

        # Update progress
        if self._session and self._engine.is_playing:
            total = self._session.total_duration
            pos = self._engine.position
            if total > 0:
                self._progress_bar.value = (pos / total) * 100

            self._time_current.text = self._format_time(pos)
            self._time_total.text = self._format_time(total)

            # Update segment info
            seg = self._engine.current_segment
            if seg:
                idx = self._engine._current_segment_idx
                total_segs = len(self._session.segments)
                self._segment_label.text = (
                    f"Segment {idx + 1}/{total_segs}: {seg.name}"
                )

        # Update waveform display with current parameters
        if self._engine.is_playing:
            self._update_waveform_preview()

    def _update_waveform_preview(self):
        """Generate a preview of the current waveform for display."""
        try:
            params = self._engine.live_params.get_snapshot()
            from core.waveforms import StereoWaveformGenerator
            gen = StereoWaveformGenerator(44100)
            stereo = gen.generate_stereo(
                waveform_a=params['waveform_a'],
                frequency_a=params['frequency_a'],
                amplitude_a=params['amplitude_a'],
                waveform_b=params['waveform_b'],
                frequency_b=params['frequency_b'],
                amplitude_b=params['amplitude_b'],
                num_samples=1000,
            )
            self._waveform_display.set_data(stereo[:, 0], stereo[:, 1])
        except Exception:
            pass

    @staticmethod
    def _format_time(seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    # ─── Public API ─────────────────────────────────────

    def load_and_play(self, session: Session):
        """Load a session and start playing."""
        self._session = session

        if self._built:
            self._session_name_label.text = session.name
            self._time_total.text = self._format_time(session.total_duration)
            self._segment_label.text = f"{len(session.segments)} Segmente"

            # Update slider positions from first segment
            if session.segments:
                seg = session.segments[0]
                self._freq_a_slider.value = float(seg.channel_a.frequency)
                self._amp_a_slider.value = float(seg.channel_a.amplitude * 100)
                self._freq_b_slider.value = float(seg.channel_b.frequency)
                self._amp_b_slider.value = float(seg.channel_b.amplitude * 100)
                self._wf_a_btn.text = seg.channel_a.waveform.value.capitalize()
                self._wf_b_btn.text = seg.channel_b.waveform.value.capitalize()

        try:
            self._engine.play_session(session)
        except Exception as e:
            self._session_name_label.text = f"Fehler: {e}"

    def load_session(self, session: Session):
        """Load a session without starting playback."""
        self._session = session
        if self._built:
            self._session_name_label.text = session.name
            self._time_total.text = self._format_time(session.total_duration)
            self._segment_label.text = f"{len(session.segments)} Segmente"
