"""
Channel Mixer Widget - Stereo channel controls for E-Stim 2B.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, StringProperty, ObjectProperty
from kivymd.uix.label import MDLabel
from kivymd.uix.slider import MDSlider
from kivymd.uix.card import MDCard


class ChannelStrip(MDCard):
    """
    A single channel control strip with amplitude and frequency controls.
    """

    channel_name = StringProperty("Kanal A")
    channel_id = StringProperty("a")
    amplitude = NumericProperty(0.7)
    frequency = NumericProperty(80.0)
    on_amplitude_change = ObjectProperty(None)
    on_frequency_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = "8dp"
        self.spacing = "4dp"
        self.size_hint_y = None
        self.height = "200dp"
        self.md_bg_color = [0.15, 0.15, 0.18, 1]
        self.radius = [8]

        self._build_ui()

    def _build_ui(self):
        # Channel label
        self.label = MDLabel(
            text=self.channel_name,
            font_style="Subtitle1",
            halign="center",
            size_hint_y=None,
            height="30dp",
            theme_text_color="Custom",
            text_color=[0.3, 0.7, 1.0, 1.0] if self.channel_id == "a" else [1.0, 0.4, 0.4, 1.0],
        )
        self.add_widget(self.label)

        # Amplitude
        amp_box = BoxLayout(orientation="horizontal", size_hint_y=None, height="50dp")
        amp_box.add_widget(MDLabel(
            text="Amplitude", size_hint_x=0.3,
            font_style="Caption", halign="left"
        ))
        self.amp_slider = MDSlider(
            min=0, max=100, value=int(self.amplitude * 100),
            size_hint_x=0.5,
            color=[0.3, 0.7, 1.0, 1.0],
        )
        self.amp_slider.bind(value=self._on_amp_change)
        amp_box.add_widget(self.amp_slider)
        self.amp_label = MDLabel(
            text=f"{int(self.amplitude * 100)}%",
            size_hint_x=0.2, halign="right", font_style="Caption"
        )
        amp_box.add_widget(self.amp_label)
        self.add_widget(amp_box)

        # Frequency
        freq_box = BoxLayout(orientation="horizontal", size_hint_y=None, height="50dp")
        freq_box.add_widget(MDLabel(
            text="Frequenz", size_hint_x=0.3,
            font_style="Caption", halign="left"
        ))
        self.freq_slider = MDSlider(
            min=2, max=300, value=int(self.frequency),
            size_hint_x=0.5,
            color=[0.3, 0.7, 1.0, 1.0],
        )
        self.freq_slider.bind(value=self._on_freq_change)
        freq_box.add_widget(self.freq_slider)
        self.freq_label = MDLabel(
            text=f"{int(self.frequency)} Hz",
            size_hint_x=0.2, halign="right", font_style="Caption"
        )
        freq_box.add_widget(self.freq_label)
        self.add_widget(freq_box)

    def _on_amp_change(self, instance, value):
        self.amplitude = value / 100.0
        self.amp_label.text = f"{int(value)}%"
        if self.on_amplitude_change:
            self.on_amplitude_change(self.channel_id, self.amplitude)

    def _on_freq_change(self, instance, value):
        self.frequency = value
        self.freq_label.text = f"{int(value)} Hz"
        if self.on_frequency_change:
            self.on_frequency_change(self.channel_id, self.frequency)
