"""
Library Screen - Browse and manage saved sessions.
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

from core.session import Session, SessionLibrary


class SessionListCard(CardBox):
    """Card representing a saved session in the library."""

    def __init__(self, session_info: dict, on_play=None, on_edit=None, on_delete=None, **kwargs):
        super().__init__(**kwargs)
        self.session_info = session_info
        self._on_play = on_play
        self._on_edit = on_edit
        self._on_delete = on_delete

        self.orientation = "horizontal"
        self.padding = dp(12)
        self.spacing = dp(8)
        self.size_hint_y = None
        self.height = dp(80)
        self.bg_color = [0.15, 0.15, 0.2, 1]
        self.radius = [dp(8)]

        self._build_ui()

    def _build_ui(self):
        # Info section
        info = MDBoxLayout(orientation="vertical", size_hint_x=0.6)
        info.add_widget(MDLabel(
            text=self.session_info.get("name", "Unbenannt"),
            font_style="Subtitle1",
            size_hint_y=None, height=dp(25),
        ))
        info.add_widget(MDLabel(
            text=f"⏱ {self.session_info.get('duration', '00:00')} | "
                 f"{self.session_info.get('segments', 0)} Segmente",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.5, 0.5, 1],
            size_hint_y=None, height=dp(20),
        ))
        desc = self.session_info.get("description", "")
        if desc:
            info.add_widget(MDLabel(
                text=desc[:60],
                font_style="Caption",
                theme_text_color="Custom",
                text_color=[0.4, 0.4, 0.4, 1],
                size_hint_y=None, height=dp(18),
            ))
        self.add_widget(info)

        # Actions
        actions = MDBoxLayout(size_hint_x=0.4)
        play_btn = MDIconButton(
            icon="play-circle",
            on_release=lambda x: self._on_play(self.session_info) if self._on_play else None,
            theme_icon_color="Custom",
            icon_color=[0.3, 0.8, 0.3, 1],
        )
        actions.add_widget(play_btn)

        edit_btn = MDIconButton(
            icon="pencil",
            on_release=lambda x: self._on_edit(self.session_info) if self._on_edit else None,
            theme_icon_color="Custom",
            icon_color=[0.3, 0.7, 1.0, 1],
        )
        actions.add_widget(edit_btn)

        delete_btn = MDIconButton(
            icon="delete",
            on_release=lambda x: self._on_delete(self.session_info) if self._on_delete else None,
            theme_icon_color="Custom",
            icon_color=[0.8, 0.3, 0.3, 1],
        )
        actions.add_widget(delete_btn)

        self.add_widget(actions)


class LibraryScreen(MDScreen):
    """Screen to browse and manage saved sessions."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "library"
        self._library = SessionLibrary("sessions")
        self._built = False

    def _open_nav(self):
        from kivymd.app import MDApp
        MDApp.get_running_app().nav_drawer.set_state("toggle")

    def on_enter(self):
        if not self._built:
            self._build_ui()
            self._built = True
        self._refresh_list()

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
            text="Bibliothek", font_style="H6", halign="center",
        ))
        refresh_btn = MDIconButton(
            icon="refresh",
            on_release=lambda x: self._refresh_list(),
            theme_icon_color="Custom",
            icon_color=[0.3, 0.7, 1.0, 1],
        )
        toolbar.add_widget(refresh_btn)
        menu_btn = MDIconButton(
            icon="menu",
            on_release=lambda x: self._open_nav(),
            theme_icon_color="Custom",
            icon_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(menu_btn)
        root.add_widget(toolbar)

        # Session list
        self._scroll = SliderFriendlyScrollView()
        self._list = MDBoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(8),
            size_hint_y=None,
            adaptive_height=True,
        )
        self._scroll.add_widget(self._list)
        root.add_widget(self._scroll)

        self.add_widget(root)

    def _refresh_list(self):
        """Reload and display all saved sessions."""
        self._list.clear_widgets()

        sessions = self._library.list_sessions()

        if not sessions:
            self._list.add_widget(MDLabel(
                text="Keine gespeicherten Sessions.\n\n"
                     "Erstelle Sessions mit dem Generator\n"
                     "oder Auto-Generator.",
                halign="center",
                font_style="Body1",
                theme_text_color="Custom",
                text_color=[0.5, 0.5, 0.5, 1],
                size_hint_y=None,
                height=dp(120),
            ))
            return

        for info in sessions:
            card = SessionListCard(
                session_info=info,
                on_play=self._play_session,
                on_edit=self._edit_session,
                on_delete=self._confirm_delete,
            )
            self._list.add_widget(card)

    def _play_session(self, info):
        """Load and play a session."""
        try:
            session = self._library.load_session(info["filename"])
            player = self.manager.get_screen("player")
            player.load_and_play(session)
            self.manager.current = "player"
        except Exception as e:
            print(f"Fehler beim Laden: {e}")

    def _edit_session(self, info):
        """Load session into session builder for editing."""
        try:
            session = self._library.load_session(info["filename"])
            builder = self.manager.get_screen("session_builder")
            builder.load_session(session)
            self.manager.current = "session_builder"
        except Exception as e:
            print(f"Fehler beim Laden: {e}")

    def _confirm_delete(self, info):
        """Show delete confirmation dialog."""
        dialog = MDDialog(
            title="Session löschen?",
            text=f"'{info.get('name', 'Unbenannt')}' wirklich löschen?",
            buttons=[
                MDFlatButton(
                    text="Abbrechen",
                    on_release=lambda x: dialog.dismiss(),
                ),
                MDRaisedButton(
                    text="Löschen",
                    md_bg_color=[0.8, 0.2, 0.2, 1],
                    on_release=lambda x: self._delete_session(info, dialog),
                ),
            ],
        )
        dialog.open()

    def _delete_session(self, info, dialog):
        """Delete a session."""
        dialog.dismiss()
        try:
            self._library.delete_session(info["filename"])
            self._refresh_list()
        except Exception as e:
            print(f"Fehler beim Löschen: {e}")
