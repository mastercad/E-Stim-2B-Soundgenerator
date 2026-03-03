"""
Session Builder Screen - Create sessions by arranging pattern segments.

Allows users to:
- Add, remove, reorder segments
- Configure each segment individually
- Set transitions between segments
- Preview and save sessions
"""

from kivy.clock import Clock
from kivy.metrics import dp
from ui.widgets.slider_scrollview import SliderFriendlyScrollView

from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from ui.widgets.card_container import CardBox
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.slider import MDSlider
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import OneLineListItem

import os

from core.waveforms import WaveformType
from core.modulation import ModulationType, ModulationParams
from core.patterns import PatternSegment, ChannelConfig, TransitionType, create_preset_patterns
from core.session import Session, SessionLibrary


class SegmentCard(CardBox):
    """Card representing a single segment in the session timeline."""

    def __init__(self, segment: PatternSegment, index: int,
                 on_edit=None, on_delete=None, on_move_up=None, on_move_down=None,
                 on_duplicate=None,
                 **kwargs):
        super().__init__(**kwargs)
        self.segment = segment
        self.index = index
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_move_up = on_move_up
        self._on_move_down = on_move_down
        self._on_duplicate = on_duplicate

        self.orientation = "vertical"
        self.padding = dp(8)
        self.spacing = dp(4)
        self.size_hint_y = None
        self.height = dp(100)
        self.bg_color = [0.15, 0.15, 0.2, 1]
        self.radius = [dp(8)]

        self._build_ui()

    def _build_ui(self):
        # Header row
        header = MDBoxLayout(size_hint_y=None, height=dp(30))
        header.add_widget(MDLabel(
            text=f"#{self.index + 1}",
            font_style="Caption",
            size_hint_x=0.1,
            theme_text_color="Custom",
            text_color=[0.5, 0.5, 0.5, 1],
        ))
        header.add_widget(MDLabel(
            text=self.segment.name,
            font_style="Subtitle2",
            size_hint_x=0.5,
        ))
        header.add_widget(MDLabel(
            text=f"{self.segment.duration:.0f}s",
            font_style="Caption",
            size_hint_x=0.15,
            halign="right",
        ))

        # Action buttons
        btn_box = MDBoxLayout(size_hint_x=0.25)
        btn_box.add_widget(MDIconButton(
            icon="arrow-up", on_release=lambda x: self._on_move_up(self.segment.id) if self._on_move_up else None,
            theme_icon_color="Custom", icon_color=[0.7, 0.7, 0.7, 1],
        ))
        btn_box.add_widget(MDIconButton(
            icon="arrow-down", on_release=lambda x: self._on_move_down(self.segment.id) if self._on_move_down else None,
            theme_icon_color="Custom", icon_color=[0.7, 0.7, 0.7, 1],
        ))
        btn_box.add_widget(MDIconButton(
            icon="pencil", on_release=lambda x: self._on_edit(self.segment) if self._on_edit else None,
            theme_icon_color="Custom", icon_color=[0.3, 0.7, 1.0, 1],
        ))
        btn_box.add_widget(MDIconButton(
            icon="content-copy", on_release=lambda x: self._on_duplicate(self.segment.id) if self._on_duplicate else None,
            theme_icon_color="Custom", icon_color=[0.5, 0.8, 0.3, 1],
        ))
        btn_box.add_widget(MDIconButton(
            icon="delete", on_release=lambda x: self._on_delete(self.segment.id) if self._on_delete else None,
            theme_icon_color="Custom", icon_color=[1.0, 0.3, 0.3, 1],
        ))
        header.add_widget(btn_box)
        self.add_widget(header)

        # Info row
        info = MDBoxLayout(size_hint_y=None, height=dp(24))
        info.add_widget(MDLabel(
            text=f"A: {self.segment.channel_a.waveform.value} @ {self.segment.channel_a.frequency:.0f}Hz",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.3, 0.6, 1.0, 0.8],
        ))
        info.add_widget(MDLabel(
            text=f"B: {self.segment.channel_b.waveform.value} @ {self.segment.channel_b.frequency:.0f}Hz",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[1.0, 0.4, 0.4, 0.8],
        ))
        self.add_widget(info)

        # Transition info
        trans_text = f"→ {self.segment.transition.value} ({self.segment.transition_duration:.1f}s)"
        if self.segment.modulation_a.mod_type != ModulationType.NONE:
            trans_text += f" | Mod: {self.segment.modulation_a.mod_type.value}"
        self.add_widget(MDLabel(
            text=trans_text,
            font_style="Caption",
            size_hint_y=None,
            height=dp(18),
            theme_text_color="Custom",
            text_color=[0.5, 0.5, 0.5, 1],
        ))


class SessionBuilderScreen(MDScreen):
    """Screen for building sessions from segments."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "session_builder"
        self._session = Session(name="Neue Session")
        self._library = SessionLibrary("sessions")
        self._presets = create_preset_patterns()
        self._built = False

    def _open_nav(self):
        from kivymd.app import MDApp
        MDApp.get_running_app().nav_drawer.set_state("toggle")

    def on_enter(self):
        if not self._built:
            self._build_ui()
            self._built = True
        self._refresh_segment_list()

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        # Toolbar
        toolbar = MDBoxLayout(
            size_hint_y=None, height=dp(56),
            md_bg_color=[0.12, 0.12, 0.15, 1],
            padding=[dp(8), 0],
        )
        back_btn = MDIconButton(
            icon="arrow-left",
            on_release=lambda x: setattr(self.manager, 'current', 'home'),
            theme_icon_color="Custom", icon_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(back_btn)
        toolbar.add_widget(MDLabel(
            text="Session Builder",
            font_style="H6", halign="center",
        ))
        save_btn = MDIconButton(
            icon="content-save",
            on_release=self._save_session,
            theme_icon_color="Custom",
            icon_color=[0.3, 0.7, 1.0, 1],
        )
        toolbar.add_widget(save_btn)
        menu_btn = MDIconButton(
            icon="menu",
            on_release=lambda x: self._open_nav(),
            theme_icon_color="Custom",
            icon_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(menu_btn)
        root.add_widget(toolbar)

        # Session info
        info_card = CardBox(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8),
            size_hint_y=None,
            height=dp(80),
            md_bg_color=[0.12, 0.12, 0.18, 1],
            radius=[dp(8)],
        )
        name_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        self._name_field = MDTextField(
            text=self._session.name,
            hint_text="Session Name",
            mode="fill",
            size_hint_x=0.7,
        )
        self._name_field.bind(text=lambda inst, val: setattr(self._session, 'name', val))
        name_box.add_widget(self._name_field)
        self._duration_label = MDLabel(
            text=f"⏱ {self._session.total_duration_formatted}",
            font_style="Subtitle1",
            halign="right",
            size_hint_x=0.3,
        )
        name_box.add_widget(self._duration_label)
        info_card.add_widget(name_box)
        root.add_widget(info_card)

        # Segment list
        self._segment_scroll = SliderFriendlyScrollView()
        self._segment_list = MDBoxLayout(
            orientation="vertical",
            padding=dp(8),
            spacing=dp(8),
            size_hint_y=None,
            adaptive_height=True,
        )
        self._segment_scroll.add_widget(self._segment_list)
        root.add_widget(self._segment_scroll)

        # Bottom actions
        bottom = MDBoxLayout(
            size_hint_y=None, height=dp(56),
            padding=dp(8), spacing=dp(8),
            md_bg_color=[0.12, 0.12, 0.15, 1],
        )

        add_btn = MDRaisedButton(
            text="+ Segment",
            md_bg_color=[0.2, 0.5, 0.2, 1],
            on_release=self._add_segment,
        )
        bottom.add_widget(add_btn)

        preset_btn = MDRaisedButton(
            text="+ Preset",
            md_bg_color=[0.3, 0.3, 0.5, 1],
            on_release=self._show_presets,
        )
        bottom.add_widget(preset_btn)

        export_btn = MDRaisedButton(
            text="💾 WAV Export",
            md_bg_color=[0.2, 0.4, 0.8, 1],
            on_release=self._export_wav,
        )
        bottom.add_widget(export_btn)

        root.add_widget(bottom)
        self.add_widget(root)

    def _refresh_segment_list(self):
        """Rebuild the segment cards list."""
        self._segment_list.clear_widgets()

        if not self._session.segments:
            self._segment_list.add_widget(MDLabel(
                text="Keine Segmente.\nFüge mit '+ Segment' oder '+ Preset' Segmente hinzu.",
                halign="center",
                font_style="Body2",
                theme_text_color="Custom",
                text_color=[0.5, 0.5, 0.5, 1],
                size_hint_y=None,
                height=dp(80),
            ))
        else:
            for i, segment in enumerate(self._session.segments):
                card = SegmentCard(
                    segment=segment,
                    index=i,
                    on_edit=self._edit_segment,
                    on_delete=self._delete_segment,
                    on_move_up=lambda sid: self._move_segment(sid, -1),
                    on_move_down=lambda sid: self._move_segment(sid, 1),
                    on_duplicate=self._duplicate_segment,
                )
                self._segment_list.add_widget(card)

        self._duration_label.text = f"⏱ {self._session.total_duration_formatted}"

    def _add_segment(self, *args):
        """Add a new default segment."""
        segment = PatternSegment(
            name=f"Segment {len(self._session.segments) + 1}",
            duration=15.0,
        )
        self._session.add_segment(segment)
        self._refresh_segment_list()

    def _show_presets(self, *args):
        """Show preset pattern selection."""
        items = []
        for key, preset in self._presets.items():
            items.append({
                "text": preset.name,
                "viewclass": "OneLineListItem",
                "on_release": lambda k=key: self._add_preset(k),
            })

        if hasattr(self, '_preset_menu'):
            self._preset_menu.dismiss()

        self._preset_menu = MDDropdownMenu(
            caller=self.children[0].children[0].children[1],  # preset button
            items=items,
            width_mult=4,
        )
        self._preset_menu.open()

    def _add_preset(self, preset_key):
        """Add a preset pattern as a new segment."""
        if hasattr(self, '_preset_menu'):
            self._preset_menu.dismiss()

        preset = self._presets[preset_key]
        # Create a copy
        new_segment = PatternSegment.from_dict(preset.to_dict())
        self._session.add_segment(new_segment)
        self._refresh_segment_list()

    def _edit_segment(self, segment):
        """Open segment editor dialog with full controls."""
        content = MDBoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(420),
            padding=[0, dp(4)],
        )

        # Name
        name_field = MDTextField(
            text=segment.name,
            hint_text="Segment Name",
            mode="fill",
            size_hint_y=None,
            height=dp(44),
        )
        content.add_widget(name_field)

        # Duration (seconds → supports long segments)
        dur_box = MDBoxLayout(size_hint_y=None, height=dp(44))
        dur_box.add_widget(MDLabel(text="Dauer (Sek):", size_hint_x=0.35, font_style="Body2"))
        dur_field = MDTextField(
            text=str(int(segment.duration)),
            hint_text="Sekunden",
            mode="fill",
            input_filter="int",
            size_hint_x=0.65,
        )
        dur_box.add_widget(dur_field)
        content.add_widget(dur_box)

        # ── Channel A ──
        content.add_widget(MDLabel(
            text="Kanal A (Links)",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.3, 0.6, 1.0, 1],
            size_hint_y=None, height=dp(20),
        ))

        wf_a_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        wf_a_box.add_widget(MDLabel(text="Wellenform:", size_hint_x=0.35, font_style="Body2"))
        wf_a_btn = MDRaisedButton(
            text=segment.channel_a.waveform.value.capitalize(),
            size_hint_x=0.65,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        _wf_a_choice = [segment.channel_a.waveform]
        wf_a_items = [
            {"text": wf.value.capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=wf: (wf_a_btn.__setattr__('text', x.value.capitalize()),
                                         _wf_a_choice.__setitem__(0, x),
                                         wf_a_menu.dismiss())}
            for wf in WaveformType if wf not in [WaveformType.CHIRP, WaveformType.BURST]
        ]
        wf_a_menu = MDDropdownMenu(caller=wf_a_btn, items=wf_a_items, width_mult=3)
        wf_a_btn.bind(on_release=lambda x: wf_a_menu.open())
        wf_a_box.add_widget(wf_a_btn)
        content.add_widget(wf_a_box)

        freq_a_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        freq_a_box.add_widget(MDLabel(text="Frequenz:", size_hint_x=0.25, font_style="Body2"))
        freq_a_slider = MDSlider(min=1, max=1000, value=float(segment.channel_a.frequency), size_hint_x=0.55)
        freq_a_lbl = MDLabel(text=f"{int(segment.channel_a.frequency)} Hz", size_hint_x=0.2, font_style="Caption", halign="right")
        freq_a_slider.bind(value=lambda i, v: setattr(freq_a_lbl, 'text', f"{int(v)} Hz"))
        freq_a_box.add_widget(freq_a_slider)
        freq_a_box.add_widget(freq_a_lbl)
        content.add_widget(freq_a_box)

        amp_a_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        amp_a_box.add_widget(MDLabel(text="Amplitude:", size_hint_x=0.25, font_style="Body2"))
        amp_a_slider = MDSlider(min=0, max=100, value=int(segment.channel_a.amplitude * 100), size_hint_x=0.55)
        amp_a_lbl = MDLabel(text=f"{int(segment.channel_a.amplitude * 100)}%", size_hint_x=0.2, font_style="Caption", halign="right")
        amp_a_slider.bind(value=lambda i, v: setattr(amp_a_lbl, 'text', f"{int(v)}%"))
        amp_a_box.add_widget(amp_a_slider)
        amp_a_box.add_widget(amp_a_lbl)
        content.add_widget(amp_a_box)

        # ── Channel B ──
        content.add_widget(MDLabel(
            text="Kanal B (Rechts)",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[1.0, 0.4, 0.4, 1],
            size_hint_y=None, height=dp(20),
        ))

        wf_b_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        wf_b_box.add_widget(MDLabel(text="Wellenform:", size_hint_x=0.35, font_style="Body2"))
        wf_b_btn = MDRaisedButton(
            text=segment.channel_b.waveform.value.capitalize(),
            size_hint_x=0.65,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        _wf_b_choice = [segment.channel_b.waveform]
        wf_b_items = [
            {"text": wf.value.capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=wf: (wf_b_btn.__setattr__('text', x.value.capitalize()),
                                         _wf_b_choice.__setitem__(0, x),
                                         wf_b_menu.dismiss())}
            for wf in WaveformType if wf not in [WaveformType.CHIRP, WaveformType.BURST]
        ]
        wf_b_menu = MDDropdownMenu(caller=wf_b_btn, items=wf_b_items, width_mult=3)
        wf_b_btn.bind(on_release=lambda x: wf_b_menu.open())
        wf_b_box.add_widget(wf_b_btn)
        content.add_widget(wf_b_box)

        freq_b_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        freq_b_box.add_widget(MDLabel(text="Frequenz:", size_hint_x=0.25, font_style="Body2"))
        freq_b_slider = MDSlider(min=1, max=1000, value=float(segment.channel_b.frequency), size_hint_x=0.55)
        freq_b_lbl = MDLabel(text=f"{int(segment.channel_b.frequency)} Hz", size_hint_x=0.2, font_style="Caption", halign="right")
        freq_b_slider.bind(value=lambda i, v: setattr(freq_b_lbl, 'text', f"{int(v)} Hz"))
        freq_b_box.add_widget(freq_b_slider)
        freq_b_box.add_widget(freq_b_lbl)
        content.add_widget(freq_b_box)

        amp_b_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        amp_b_box.add_widget(MDLabel(text="Amplitude:", size_hint_x=0.25, font_style="Body2"))
        amp_b_slider = MDSlider(min=0, max=100, value=int(segment.channel_b.amplitude * 100), size_hint_x=0.55)
        amp_b_lbl = MDLabel(text=f"{int(segment.channel_b.amplitude * 100)}%", size_hint_x=0.2, font_style="Caption", halign="right")
        amp_b_slider.bind(value=lambda i, v: setattr(amp_b_lbl, 'text', f"{int(v)}%"))
        amp_b_box.add_widget(amp_b_slider)
        amp_b_box.add_widget(amp_b_lbl)
        content.add_widget(amp_b_box)

        # ── Transition ──
        trans_box = MDBoxLayout(size_hint_y=None, height=dp(40))
        trans_box.add_widget(MDLabel(text="Übergang:", size_hint_x=0.35, font_style="Body2"))
        trans_btn = MDRaisedButton(
            text=segment.transition.value.capitalize(),
            size_hint_x=0.65,
            md_bg_color=[0.2, 0.2, 0.25, 1],
        )
        _trans_choice = [segment.transition]
        trans_items = [
            {"text": t.value.replace("_", " ").capitalize(), "viewclass": "OneLineListItem",
             "on_release": lambda x=t: (trans_btn.__setattr__('text', x.value.replace('_', ' ').capitalize()),
                                        _trans_choice.__setitem__(0, x),
                                        trans_menu.dismiss())}
            for t in TransitionType
        ]
        trans_menu = MDDropdownMenu(caller=trans_btn, items=trans_items, width_mult=3)
        trans_btn.bind(on_release=lambda x: trans_menu.open())
        trans_box.add_widget(trans_btn)
        content.add_widget(trans_box)

        def save_changes(*a):
            segment.name = name_field.text
            try:
                segment.duration = max(1.0, float(dur_field.text))
            except ValueError:
                pass
            segment.channel_a.waveform = _wf_a_choice[0]
            segment.channel_a.frequency = float(freq_a_slider.value)
            segment.channel_a.amplitude = float(amp_a_slider.value) / 100.0
            segment.channel_b.waveform = _wf_b_choice[0]
            segment.channel_b.frequency = float(freq_b_slider.value)
            segment.channel_b.amplitude = float(amp_b_slider.value) / 100.0
            segment.transition = _trans_choice[0]
            self._refresh_segment_list()
            dialog.dismiss()

        dialog = MDDialog(
            title="Segment bearbeiten",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Abbrechen", on_release=lambda x: dialog.dismiss()),
                MDRaisedButton(text="Speichern", on_release=save_changes),
            ],
        )
        dialog.open()

    def _delete_segment(self, segment_id):
        """Delete a segment."""
        self._session.remove_segment(segment_id)
        self._refresh_segment_list()

    def _duplicate_segment(self, segment_id):
        """Duplicate a segment and insert after the original."""
        self._session.duplicate_segment(segment_id)
        self._refresh_segment_list()

    def _move_segment(self, segment_id, direction):
        """Move a segment up or down."""
        for i, seg in enumerate(self._session.segments):
            if seg.id == segment_id:
                new_idx = i + direction
                if 0 <= new_idx < len(self._session.segments):
                    self._session.move_segment(segment_id, new_idx)
                    self._refresh_segment_list()
                break

    def _save_session(self, *args):
        """Save the current session."""
        self._session.name = self._name_field.text
        filepath = self._library.save_session(self._session)
        print(f"Session gespeichert: {filepath}")

    def _export_wav(self, *args):
        """Export session as WAV."""
        if not self._session.segments:
            return

        from core.export import AudioExporter
        exporter = AudioExporter()
        filepath = os.path.join("sessions", f"{self._session.name.replace(' ', '_').lower()}.wav")
        try:
            exporter.export_session(self._session, filepath)
            print(f"WAV exportiert: {filepath}")
        except Exception as e:
            print(f"Export-Fehler: {e}")

    def load_session(self, session: Session):
        """Load an existing session for editing."""
        self._session = session
        if self._built:
            self._name_field.text = session.name
            self._refresh_segment_list()
