"""
Android Audio Backend for E-Stim 2B Sound Generator.

Uses Android's AudioTrack via pyjnius to output real-time audio,
since sounddevice/PortAudio is not available on Android.
"""

import threading
import numpy as np
from typing import Optional, Callable


def is_android() -> bool:
    """Check if we're running on Android."""
    try:
        import android  # noqa: F401
        return True
    except ImportError:
        pass
    try:
        from jnius import autoclass  # noqa: F401
        return True
    except ImportError:
        return False


class AndroidAudioStream:
    """
    Real-time audio output stream for Android using AudioTrack.

    Mimics the sounddevice.OutputStream interface so the AudioEngine
    can use it as a drop-in replacement.
    """

    def __init__(
        self,
        samplerate: int = 44100,
        channels: int = 2,
        blocksize: int = 1024,
        dtype: str = 'float32',
        callback: Optional[Callable] = None,
    ):
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = blocksize
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Android AudioTrack setup
        from jnius import autoclass

        self.AudioTrack = autoclass('android.media.AudioTrack')
        self.AudioFormat = autoclass('android.media.AudioFormat')
        self.AudioManager = autoclass('android.media.AudioManager')

        # Channel config
        if channels == 2:
            self._channel_config = self.AudioFormat.CHANNEL_OUT_STEREO
        else:
            self._channel_config = self.AudioFormat.CHANNEL_OUT_MONO

        # Encoding: 16-bit PCM (most compatible)
        self._encoding = self.AudioFormat.ENCODING_PCM_16BIT

        # Calculate minimum buffer size
        min_buf = self.AudioTrack.getMinBufferSize(
            samplerate,
            self._channel_config,
            self._encoding,
        )
        # Use at least 2x blocksize for smooth playback
        self._buffer_size = max(min_buf, blocksize * channels * 2 * 2)

        # Create AudioTrack
        self._track = self.AudioTrack(
            self.AudioManager.STREAM_MUSIC,
            samplerate,
            self._channel_config,
            self._encoding,
            self._buffer_size,
            self.AudioTrack.MODE_STREAM,
        )

    def start(self):
        """Start the audio stream."""
        if self._running:
            return
        self._running = True
        self._track.play()
        self._thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the audio stream."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            self._track.stop()
        except Exception:
            pass

    def close(self):
        """Close and release resources."""
        self.stop()
        try:
            self._track.release()
        except Exception:
            pass

    def _audio_loop(self):
        """Main audio generation loop running in a background thread."""
        # Pre-allocate output buffer
        outdata = np.zeros((self.blocksize, self.channels), dtype=np.float32)

        while self._running:
            if self.callback:
                try:
                    # Call the same callback interface as sounddevice
                    self.callback(outdata, self.blocksize, None, None)
                except Exception as e:
                    outdata[:] = 0
                    print(f"Android Audio Callback Fehler: {e}")

                # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767]
                int_data = (outdata * 32767).astype(np.int16)

                # Interleave if needed (AudioTrack expects interleaved)
                if self.channels == 2:
                    # outdata shape: (blocksize, 2) → interleaved: [L, R, L, R, ...]
                    interleaved = int_data.flatten()
                else:
                    interleaved = int_data.flatten()

                # Convert to bytes and write to AudioTrack
                audio_bytes = interleaved.tobytes()
                self._track.write(audio_bytes, 0, len(audio_bytes))
            else:
                # No callback - output silence
                import time
                time.sleep(self.blocksize / self.samplerate)


def create_audio_stream(
    samplerate: int = 44100,
    channels: int = 2,
    blocksize: int = 1024,
    dtype: str = 'float32',
    callback: Callable = None,
):
    """
    Factory function: creates the appropriate audio stream for the platform.

    On Android → AndroidAudioStream (AudioTrack)
    On Desktop → sounddevice.OutputStream (PortAudio)
    """
    if is_android():
        stream = AndroidAudioStream(
            samplerate=samplerate,
            channels=channels,
            blocksize=blocksize,
            dtype=dtype,
            callback=callback,
        )
        return stream
    else:
        import sounddevice as sd
        stream = sd.OutputStream(
            samplerate=samplerate,
            channels=channels,
            blocksize=blocksize,
            dtype=dtype,
            callback=callback,
            latency='high',  # prefer stability over low latency
        )
        return stream
