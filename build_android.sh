#!/bin/bash
# ============================================================
#  E-Stim 2B Sound Generator — Android APK Build-Skript
# ============================================================
#
#  Dieses Skript baut die Android-APK auf deinem Linux-Rechner.
#  Die APK wird dann auf das Android-Gerät übertragen.
#
#  Voraussetzungen (werden bei Bedarf installiert):
#  - Python 3.8+
#  - Buildozer
#  - Android SDK/NDK (wird automatisch von Buildozer heruntergeladen)
#  - Systemabhängigkeiten (siehe unten)
#
#  Nutzung:
#    chmod +x build_android.sh
#    ./build_android.sh
#
# ============================================================

set -e

echo "============================================================"
echo "  E-Stim 2B Sound Generator — Android APK Builder"
echo "============================================================"
echo ""

# ─── Farben ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ─── Zum Projektverzeichnis wechseln ────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo -e "${GREEN}Projektverzeichnis:${NC} $SCRIPT_DIR"
echo ""

# ─── Schritt 1: System-Abhängigkeiten prüfen ────────────────
echo -e "${YELLOW}[1/5] Prüfe System-Abhängigkeiten...${NC}"

MISSING_DEPS=()

# Prüfe benötigte Pakete
for cmd in git zip unzip java; do
    if ! command -v "$cmd" &> /dev/null; then
        MISSING_DEPS+=("$cmd")
    fi
done

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo -e "${RED}Fehlende Abhängigkeiten: ${MISSING_DEPS[*]}${NC}"
    echo ""
    echo "Installiere mit:"
    echo "  sudo apt update && sudo apt install -y \\"
    echo "    git zip unzip openjdk-17-jdk python3-pip \\"
    echo "    autoconf automake libtool pkg-config \\"
    echo "    zlib1g-dev libncurses5-dev libncursesw5-dev \\"
    echo "    libtinfo5 cmake libffi-dev libssl-dev \\"
    echo "    libltdl-dev libgles2-mesa-dev"
    echo ""
    echo "Dann starte dieses Skript erneut."
    exit 1
fi

echo -e "${GREEN}  ✓ Alle System-Abhängigkeiten vorhanden${NC}"

# ─── Schritt 2: Buildozer installieren ───────────────────────
echo -e "${YELLOW}[2/5] Prüfe Buildozer...${NC}"

if ! command -v buildozer &> /dev/null; then
    echo "  Installiere Buildozer..."
    # Wenn eine virtualenv aktiv ist → dort installieren, sonst --user
    if [ -n "$VIRTUAL_ENV" ]; then
        pip install setuptools buildozer
    else
        pip install --user setuptools buildozer
        export PATH="$HOME/.local/bin:$PATH"
    fi
else
    # Sicherstellen, dass setuptools (distutils-Ersatz für Python 3.12+) vorhanden ist
    if ! python3 -c "import distutils" 2>/dev/null; then
        echo "  Installiere setuptools (distutils für Python 3.12+)..."
        if [ -n "$VIRTUAL_ENV" ]; then
            pip install setuptools
        else
            pip install --user setuptools
        fi
    fi
fi

if ! command -v buildozer &> /dev/null; then
    echo -e "${RED}Buildozer konnte nicht gefunden werden.${NC}"
    echo "Füge ~/.local/bin zu deinem PATH hinzu:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    exit 1
fi

echo -e "${GREEN}  ✓ Buildozer $(buildozer version 2>&1 | head -1)${NC}"

# ─── Schritt 3: Cython installieren ─────────────────────────
echo -e "${YELLOW}[3/5] Prüfe Cython...${NC}"

if ! python3 -c "import Cython" 2>/dev/null; then
    echo "  Installiere Cython..."
    if [ -n "$VIRTUAL_ENV" ]; then
        pip install cython
    else
        pip install --user cython
    fi
fi

echo -e "${GREEN}  ✓ Cython vorhanden${NC}"

# ─── Schritt 4: APK bauen ───────────────────────────────────
echo ""
echo -e "${YELLOW}[4/5] Baue Android APK...${NC}"
echo "  (Erster Build kann 15-30 Minuten dauern — SDK/NDK wird heruntergeladen)"
echo ""

buildozer android debug 2>&1 | tee build.log

# ─── Schritt 5: Ergebnis ────────────────────────────────────
echo ""
APK_PATH=$(find bin/ -name "*.apk" -type f 2>/dev/null | head -1)

if [ -n "$APK_PATH" ]; then
    APK_SIZE=$(du -h "$APK_PATH" | cut -f1)
    echo "============================================================"
    echo -e "${GREEN}  ✓ APK erfolgreich gebaut!${NC}"
    echo ""
    echo -e "  Datei:  ${GREEN}$APK_PATH${NC}"
    echo -e "  Größe:  $APK_SIZE"
    echo ""
    echo "  Installation auf Android-Gerät:"
    echo ""
    echo "  Option A — Per USB-Kabel (ADB):"
    echo "    adb install $APK_PATH"
    echo ""
    echo "  Option B — Per Datei-Transfer:"
    echo "    1. Kopiere die APK-Datei auf dein Android-Gerät"
    echo "       (USB, Cloud, Bluetooth, ...)"
    echo "    2. Öffne die Datei auf dem Gerät"
    echo "    3. Erlaube 'Installation aus unbekannten Quellen'"
    echo "    4. Installiere die App"
    echo ""
    echo "============================================================"
else
    echo -e "${RED}  ✗ Build fehlgeschlagen! Siehe build.log für Details.${NC}"
    exit 1
fi
