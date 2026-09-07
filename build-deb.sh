#!/bin/bash
set -euo pipefail

VERSION="1.0.0"
ARCH="amd64"
PKG_NAME="PLUTO"
DIST_DIR="dist"
DEB_DIR="${DIST_DIR}/debian"
DEB_FILE="${DIST_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "=== Building PLUTO Desktop .deb ==="

# Ensure build artifacts exist
if [ ! -f "package.json" ]; then
    echo "Error: Must run from repository root."
    exit 1
fi

# Clean previous package build
rm -rf "${DEB_DIR}" "${DEB_FILE}"
mkdir -p "${DEB_DIR}/DEBIAN"

# Build frontend production export if needed
if [ ! -d "out" ] || [ "src/app/page.tsx" -nt "out/index.html" ]; then
    echo "Building frontend (next build --turbopack) ..."
    npm run build
fi

# Assemble package directories
echo "Assembling package contents ..."
mkdir -p "${DEB_DIR}/opt/pluto/out"
mkdir -p "${DEB_DIR}/opt/pluto/pluto-backend"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/usr/share/applications"

# Icon sizes in hicolor
for s in 16 22 24 32 40 48 64 96 128 256; do
    mkdir -p "${DEB_DIR}/usr/share/icons/hicolor/${s}x${s}/apps"
done

# Copy production frontend (exclude unused massive 3D assets to keep .deb small)
cp -r out/* "${DEB_DIR}/opt/pluto/out/" || true
# Remove the huge scene binary that is not referenced by UI components
rm -rf "${DEB_DIR}/opt/pluto/out/a_windy_day/scene.bin" || true
# Keep the rest of a_windy_day in case it's needed (license, gltf)

# Copy backend source for optional backend use
cp -r pluto-backend/* "${DEB_DIR}/opt/pluto/pluto-backend/" 2>/dev/null || true

# Copy application wrapper and original logo
cp pluto-app.py "${DEB_DIR}/opt/pluto/pluto-app.py"
chmod +x "${DEB_DIR}/opt/pluto/pluto-app.py"
cp pluto.png "${DEB_DIR}/opt/pluto/pluto.png"

# Include the native desktop runtime venv (pywebview + bottle)
echo "Copying native desktop runtime venv ..."
cp -r /tmp/pluto_venv "${DEB_DIR}/opt/pluto/venv"

# Launcher executable
cp pluto-launcher.sh "${DEB_DIR}/usr/bin/pluto"
chmod +x "${DEB_DIR}/usr/bin/pluto"

# Desktop entry
cp pluto.desktop "${DEB_DIR}/usr/share/applications/pluto.desktop"

# Icons from pluto.png (preserve design; generate required sizes)
for s in 16 22 24 32 40 48 64 96 128 256; do
    cp "/tmp/icons/${s}x${s}/pluto.png" \
        "${DEB_DIR}/usr/share/icons/hicolor/${s}x${s}/apps/pluto.png"
done
# Ensure 256x256 also has the original high-res logo
cp pluto.png "${DEB_DIR}/usr/share/icons/hicolor/256x256/apps/pluto.png"

# DEBIAN control
echo "Writing DEBIAN/control ..."
cat > "${DEB_DIR}/DEBIAN/control" <<EOF
Package: pluto
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), python3-pip, python3-gi, gir1.2-gtk-3.0, libgtk-3-0, libwebkit2gtk-4.0-37, libgl1
Maintainer: PLUTO AI Team <pluto@example.com>
Description: PLUTO - Real Linux Desktop AI Assistant
 PLUTO is a true Linux desktop application with native window,
 voice interface, command bar, orb animations, and system tools.
 The production build is packaged independently — no Chrome redirect,
 no localhost dependency, no development server required.
 .
 Includes the existing React/Next.js UI preserved as static assets.
Homepage: https://github.com/ASIM7815/pluto
EOF

# Post-install script (update caches, optionally install backend venv)
echo "Writing DEBIAN/postinst ..."
cat > "${DEB_DIR}/DEBIAN/postinst" <<'EOF'
#!/bin/bash
set -e
echo "Installing PLUTO desktop application..."

# Refresh icon caches
if command -v update-icon-caches >/dev/null 2>&1; then
    update-icon-caches /usr/share/icons/hicolor || true
fi

# Refresh desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi

# If backend source is present but venv missing, create it (optional)
if [ -d "/opt/pluto/pluto-backend" ] && [ ! -d "/opt/pluto/pluto-backend/venv" ]; then
    echo "Setting up PLUTO backend environment (optional)..."
    cd /opt/pluto/pluto-backend
    python3 -m venv venv 2>/dev/null || true
    if [ -f "venv/bin/pip" ]; then
        venv/bin/pip install --quiet --upgrade pip 2>/dev/null || true
        venv/bin/pip install --quiet -r requirements.txt 2>/dev/null || true
    fi
fi

echo ""
echo "✅ PLUTO installed successfully!"
echo "Launch from Applications menu or run: pluto"
echo ""
exit 0
EOF
chmod 755 "${DEB_DIR}/DEBIAN/postinst"

# Pre-remove script (minimal)
echo "Writing DEBIAN/prerm ..."
cat > "${DEB_DIR}/DEBIAN/prerm" <<'EOF'
#!/bin/bash
echo "Removing PLUTO..."
exit 0
EOF
chmod 755 "${DEB_DIR}/DEBIAN/prerm"

mkdir -p "${DIST_DIR}"

echo "Building .deb package ..."
dpkg-deb --build "${DEB_DIR}" "${DEB_FILE}"

echo ""
echo "========================================"
echo "✅ PLUTO .deb package built successfully"
echo "File: ${DEB_FILE}"
ls -lh "${DEB_FILE}"
echo "========================================"
