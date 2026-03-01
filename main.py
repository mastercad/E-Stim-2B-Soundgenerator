#!/usr/bin/env python3
"""
E-Stim 2B Sound Generator
==========================

Cross-platform application for generating custom audio stimulation
patterns for the E-Stim 2B electrostimulation device.

Left channel  → E-Stim Channel A
Right channel → E-Stim Channel B

Usage:
    python main.py
"""

import os
import sys

# Ensure the project root is on the Python path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ─── Kivy Configuration (must be set before importing kivy) ──────────
os.environ.setdefault("KIVY_LOG_LEVEL", "info")

from kivy.config import Config
Config.set("graphics", "width", "420")
Config.set("graphics", "height", "750")
Config.set("graphics", "resizable", "1")
Config.set("graphics", "minimum_width", "360")
Config.set("graphics", "minimum_height", "600")
Config.set("input", "mouse", "mouse,multitouch_on_demand")

# ─── KivyMD App ──────────────────────────────────────────────────────
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, NoTransition

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.navigationdrawer import MDNavigationLayout, MDNavigationDrawer
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget
from kivymd.uix.label import MDLabel

# Import screens
from ui.screens.home_screen import HomeScreen
from ui.screens.generator_screen import GeneratorScreen
from ui.screens.session_builder_screen import SessionBuilderScreen
from ui.screens.auto_generator_screen import AutoGeneratorScreen
from ui.screens.player_screen import PlayerScreen
from ui.screens.library_screen import LibraryScreen
from ui.screens.settings_screen import SettingsScreen


class ContentNavigationDrawer(MDBoxLayout):
    """Content for the navigation drawer."""
    pass


class EStimSoundGeneratorApp(MDApp):
    """Main application class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "E-Stim 2B Sound Generator"
        self.icon = ""  # TODO: Add app icon

    def build(self):
        # Theme configuration
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Cyan"
        self.theme_cls.material_style = "M3"

        # Load KV design file
        kv_path = os.path.join(PROJECT_ROOT, "ui", "app.kv")
        if os.path.exists(kv_path):
            Builder.load_file(kv_path)

        # Build the root layout
        root = self._build_root()

        # Create required directories
        self._ensure_directories()

        return root

    def _build_root(self):
        """Build the root widget with navigation drawer and screen manager."""

        # Root: nav layout (no global toolbar — each screen has its own)
        root_box = MDBoxLayout(orientation="vertical")

        # Navigation layout (requires ScreenManager + MDNavigationDrawer as children)
        nav_layout = MDNavigationLayout()

        # Screen Manager
        self.sm = ScreenManager(transition=NoTransition())

        # Register all screens
        self.sm.add_widget(HomeScreen())
        self.sm.add_widget(GeneratorScreen())
        self.sm.add_widget(SessionBuilderScreen())
        self.sm.add_widget(AutoGeneratorScreen())
        self.sm.add_widget(PlayerScreen())
        self.sm.add_widget(LibraryScreen())
        self.sm.add_widget(SettingsScreen())

        nav_layout.add_widget(self.sm)

        # Navigation Drawer
        self.nav_drawer = MDNavigationDrawer(
            radius=[0, 16, 16, 0],
        )

        drawer_content = MDBoxLayout(
            orientation="vertical",
            padding="8dp",
            spacing="4dp",
        )

        # Drawer Header
        header = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height="100dp",
            padding=["12dp", "20dp", "12dp", "8dp"],
        )
        header.add_widget(MDLabel(
            text="E-Stim 2B",
            font_style="H6",
            size_hint_y=None,
            height="36dp",
        ))
        header.add_widget(MDLabel(
            text="Sound Generator v1.0",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=[0.5, 0.5, 0.5, 1],
            size_hint_y=None,
            height="24dp",
        ))
        drawer_content.add_widget(header)

        # Navigation items
        nav_items = [
            ("home", "home", "Startseite"),
            ("generator", "sine-wave", "Generator"),
            ("session_builder", "playlist-music", "Session Builder"),
            ("auto_generator", "auto-fix", "Auto-Generator"),
            ("player", "play-circle", "Player"),
            ("library", "folder-music", "Bibliothek"),
            ("settings", "cog", "Einstellungen"),
        ]

        from kivymd.uix.list import MDList
        from kivy.uix.scrollview import ScrollView

        scroll = ScrollView()
        nav_list = MDList()

        for screen_name, icon_name, label in nav_items:
            item = OneLineIconListItem(
                text=label,
                on_release=lambda x, sn=screen_name: self._navigate_to(sn),
            )
            item.add_widget(IconLeftWidget(icon=icon_name))
            nav_list.add_widget(item)

        scroll.add_widget(nav_list)
        drawer_content.add_widget(scroll)

        self.nav_drawer.add_widget(drawer_content)
        nav_layout.add_widget(self.nav_drawer)

        root_box.add_widget(nav_layout)
        return root_box

    def _toggle_nav(self):
        """Toggle navigation drawer open/close."""
        self.nav_drawer.set_state("toggle")

    def _navigate_to(self, screen_name: str):
        """Navigate to a screen and close the drawer."""
        self.sm.current = screen_name
        self.nav_drawer.set_state("close")

    def _ensure_directories(self):
        """Create required directories if they don't exist."""
        dirs = [
            os.path.join(PROJECT_ROOT, "sessions"),
            os.path.join(PROJECT_ROOT, "presets"),
            os.path.join(PROJECT_ROOT, "assets"),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def on_stop(self):
        """Clean up when app closes."""
        # Stop any running audio engines in screens
        for screen in self.sm.screens:
            if hasattr(screen, '_engine') and screen._engine is not None:
                try:
                    screen._engine.stop()
                except Exception:
                    pass


def main():
    """Application entry point."""
    print("=" * 50)
    print("  E-Stim 2B Sound Generator v1.0.0")
    print("  Cross-Platform Audio Stimulation Tool")
    print("=" * 50)
    print()
    print("⚠  SICHERHEITSHINWEIS:")
    print("   Beginne IMMER mit niedriger Intensität!")
    print("   Erhöhe die Stärke langsam am E-Stim 2B Gerät.")
    print()

    app = EStimSoundGeneratorApp()
    app.run()


if __name__ == "__main__":
    main()
