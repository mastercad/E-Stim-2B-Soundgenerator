[app]

# (str) Title of your application
title = E-Stim 2B Sound Generator

# (str) Package name
package.name = estim2bsoundgen

# (str) Package domain (needed for android/ios packaging)
package.domain = org.estim2b

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
# Note: sounddevice is NOT included - Android uses AudioTrack via pyjnius instead
# Note: scipy removed — Fortran/OpenBLAS can't cross-compile for Android ARM.
#       export.py has a pure-Python WAV fallback when scipy is unavailable.
requirements = python3,kivy==2.3.1,kivymd==1.1.1,numpy,pillow,pyjnius,sdl2_ttf==2.20.0

# (str) Supported orientation (landscape, sensorLandscape, portrait, all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 28c

# (str) The Android arch to build for
android.archs = arm64-v8a,armeabi-v7a

# (bool) Enable AndroidX support
android.enable_androidx = True

# (str) python-for-android branch
p4a.branch = develop

# (str) Bootstrap to use for android builds
p4a.bootstrap = sdl2

# (str) presplash of the application
#presplash.filename = %(source.dir)s/assets/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/assets/icon.png

# (str) Supported platforms (in addition to Android)
# Supported: linux, macosx, win
# osx.python_version = 3
# osx.kivy_version = 2.2.1

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
