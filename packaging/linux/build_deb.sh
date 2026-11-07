#!/usr/bin/env bash
# Crea il pacchetto .deb di Charta (Debian, Ubuntu, Linux Mint...) a partire
# dalla cartella dist/Charta prodotta da PyInstaller.
#   bash packaging/linux/build_deb.sh 0.3.0
set -euo pipefail

VERSION="${1:?indica la versione, es. 0.3.0}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$ROOT/build/deb/charta_${VERSION}_amd64"
rm -rf "$PKG"

mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/mime/packages" \
         "$PKG/usr/share/icons/hicolor/512x512/apps" \
         "$PKG/usr/share/icons/hicolor/512x512/mimetypes"

cp -r "$ROOT/dist/Charta" "$PKG/opt/charta"
ln -s /opt/charta/Charta "$PKG/usr/bin/charta"
install -m 644 "$ROOT/packaging/linux/charta.desktop" "$PKG/usr/share/applications/charta.desktop"
install -m 644 "$ROOT/packaging/linux/charta-mime.xml" "$PKG/usr/share/mime/packages/charta.xml"
install -m 644 "$ROOT/packaging/icons/charta.png" "$PKG/usr/share/icons/hicolor/512x512/apps/charta.png"
install -m 644 "$ROOT/packaging/icons/charta.png" \
        "$PKG/usr/share/icons/hicolor/512x512/mimetypes/application-x-charta.png"

SIZE=$(du -sk "$PKG" | cut -f1)
cat > "$PKG/DEBIAN/control" <<EOF
Package: charta
Version: $VERSION
Section: graphics
Priority: optional
Architecture: amd64
Installed-Size: $SIZE
Depends: libegl1, libgl1, libxkbcommon0, libfontconfig1, libdbus-1-3
Recommends: libxkbcommon-x11-0, libxcb-cursor0, libreoffice-draw, ghostscript
Maintainer: EurekaFoundation <https://github.com/EurekaFoundation>
Homepage: https://github.com/EurekaFoundation/charta
Description: impaginazione libera, alternativa a Microsoft Publisher
 Charta crea volantini, locandine, brochure, giornalini, menu e attestati:
 testo che scorre tra cornici, tabelle, stampa unione da CSV/Excel,
 PDF per la tipografia (anche CMYK) e importazione dei file .pub.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v update-mime-database >/dev/null && update-mime-database /usr/share/mime || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
exit 0
EOF
cp "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

mkdir -p "$ROOT/dist"
dpkg-deb --build --root-owner-group "$PKG" "$ROOT/dist/Charta-${VERSION}-linux-amd64.deb"
echo "Creato: dist/Charta-${VERSION}-linux-amd64.deb"
