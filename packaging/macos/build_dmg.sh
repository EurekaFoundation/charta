#!/usr/bin/env bash
# Crea l'immagine disco .dmg di Charta a partire da dist/Charta.app (PyInstaller).
#   bash packaging/macos/build_dmg.sh 0.3.0
set -euo pipefail

VERSION="${1:?indica la versione, es. 0.3.0}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/Charta.app"
STAGE="$ROOT/build/dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE"

# i file .charta si aprono con Charta (dichiarati nell'Info.plist)
PLIST="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes array" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0 dict" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeName string 'Charta Document'" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Editor" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions array" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:0 string charta" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDocumentTypes:0:CFBundleTypeExtensions:1 string pub" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST"
# firma ad hoc: senza, sui Mac con chip Apple l'app potrebbe non avviarsi
codesign --force --deep --sign - "$APP"

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applicazioni"
hdiutil create -volname "Charta $VERSION" -srcfolder "$STAGE" -ov -format UDZO \
  "$ROOT/dist/Charta-${VERSION}-macos.dmg"
echo "Creato: dist/Charta-${VERSION}-macos.dmg"
