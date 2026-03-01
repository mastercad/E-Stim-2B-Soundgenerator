"""
Home Screen - Main navigation hub.
"""

from kivymd.uix.screen import MDScreen
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel, MDIcon
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp


class MenuCard(MDCard):
    """A clickable menu card for navigation."""

    def __init__(self, title, icon, description, screen_name, screen_manager, **kwargs):
        super().__init__(**kwargs)
        self.screen_name = screen_name
        self.screen_manager = screen_manager
        self.orientation = "vertical"
        self.padding = dp(16)
        self.spacing = dp(8)
        self.size_hint = (1, None)
        self.height = dp(120)
        self.md_bg_color = [0.15, 0.15, 0.2, 1]
        self.radius = [dp(12)]
        self.ripple_behavior = True

        # Icon
        icon_widget = MDIcon(
            icon=icon,
            halign="center",
            font_size=dp(36),
            theme_text_color="Custom",
            text_color=[0.3, 0.7, 1.0, 1.0],
        )
        self.add_widget(icon_widget)

        # Title
        title_label = MDLabel(
            text=title,
            halign="center",
            font_style="Subtitle1",
            theme_text_color="Custom",
            text_color=[1, 1, 1, 1],
        )
        self.add_widget(title_label)

        # Description
        desc_label = MDLabel(
            text=description,
            halign="center",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
        )
        self.add_widget(desc_label)

    def on_release(self):
        self.screen_manager.current = self.screen_name


class HomeScreen(MDScreen):
    """Main menu screen with navigation cards."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "home"

    def on_enter(self):
        """Build UI when screen is entered for the first time."""
        if not self.children:
            self._build_ui()

    def _open_nav(self):
        from kivymd.app import MDApp
        MDApp.get_running_app().nav_drawer.set_state("toggle")

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical")

        # Toolbar with menu button
        toolbar = MDBoxLayout(
            size_hint_y=None, height=dp(56),
            md_bg_color=[0.12, 0.12, 0.15, 1],
            padding=[dp(8), 0],
        )
        menu_btn = MDIconButton(
            icon="menu",
            on_release=lambda x: self._open_nav(),
            theme_icon_color="Custom",
            icon_color=[1, 1, 1, 1],
        )
        toolbar.add_widget(menu_btn)
        toolbar.add_widget(MDLabel(
            text="E-Stim 2B Sound Generator",
            font_style="H6",
            halign="center",
        ))
        toolbar.add_widget(MDBoxLayout(size_hint_x=None, width=dp(48)))
        root.add_widget(toolbar)

        layout = MDBoxLayout(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(16),
        )

        # Header
        header = MDLabel(
            text="E-Stim 2B Sound Generator",
            halign="center",
            font_style="H5",
            size_hint_y=None,
            height=dp(60),
            theme_text_color="Custom",
            text_color=[0.3, 0.7, 1.0, 1.0],
        )
        layout.add_widget(header)

        subtitle = MDLabel(
            text="Erstelle & spiele individuelle Stimulationsmuster",
            halign="center",
            font_style="Body2",
            size_hint_y=None,
            height=dp(30),
            theme_text_color="Custom",
            text_color=[0.7, 0.7, 0.7, 1],
        )
        layout.add_widget(subtitle)

        # Menu grid
        grid = GridLayout(
            cols=2,
            spacing=dp(12),
            padding=dp(8),
        )

        sm = self.manager

        menu_items = [
            ("Generator", "sine-wave", "Wellenformen\nmanuell erstellen", "generator"),
            ("Session Builder", "playlist-music", "Sessions aus\nSegmenten bauen", "session_builder"),
            ("Auto-Generator", "auto-fix", "Sessions\nautomatisch erzeugen", "auto_generator"),
            ("Player", "play-circle", "Sessions abspielen\n& live anpassen", "player"),
            ("Bibliothek", "folder-music", "Gespeicherte\nSessions verwalten", "library"),
            ("Einstellungen", "cog", "Audio & App\nkonfigurieren", "settings"),
        ]

        for title, icon, desc, screen in menu_items:
            card = MenuCard(title, icon, desc, screen, sm)
            grid.add_widget(card)

        layout.add_widget(grid)
        root.add_widget(layout)
        self.add_widget(root)
