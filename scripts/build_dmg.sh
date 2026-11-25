#!/usr/bin/env bash
# ============================================================
# Loki Alfred - build an (unsigned, ad-hoc signed) macOS .dmg
#
# Usage (from the repo root):
#   ./scripts/build_dmg.sh
#   CI=false ./scripts/build_dmg.sh   # also lay out the DMG window via Finder
#
# Output:
#   Alfred/src-tauri/target/release/bundle/dmg/*.dmg
#
# Prerequisites (this script checks but does not install them):
#   - Xcode Command Line Tools   (xcode-select --install)
#   - Python 3 (python.org installer recommended)
#   - Node.js + npm
#   - Rust (rustup)
# ============================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_DIR="$PROJECT_ROOT/Alfred"
TAURI_SRC="$TAURI_DIR/src-tauri"
VENV_DIR="$PROJECT_ROOT/.venv-build"
PYTHON_BIN="${PYTHON_BIN:-python3}"

step()    { echo; echo "==> $1"; }
success() { echo "✓ $1"; }
fail()    { echo; echo "ERROR: $1" >&2; exit 1; }
need()    { command -v "$1" >/dev/null 2>&1 || fail "'$1' not found. $2"; }

# ------------------------------------------------------------
step "Checking environment"
# ------------------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]] || fail "This script must run on macOS."
xcode-select -p >/dev/null 2>&1 || fail "Xcode Command Line Tools missing. Run: xcode-select --install"

need "$PYTHON_BIN" "Install Python 3 (python.org installer recommended)."
need node  "Install Node.js."
need npm   "Install Node.js."
need cargo "Install Rust: https://rustup.rs"
need rustc "Install Rust: https://rustup.rs"

PY_PATH="$(command -v "$PYTHON_BIN")"
echo "macOS   : $(sw_vers -productVersion) ($(uname -m))"
echo "Python  : $("$PYTHON_BIN" --version) at $PY_PATH"
echo "Node    : $(node --version)"
echo "Rust    : $(rustc --version)"

if [[ "$PY_PATH" == /opt/homebrew/* || "$PY_PATH" == /usr/local/Cellar/* ]]; then
    echo "⚠ Homebrew Python detected. The app may only run on this macOS version or newer."
    echo "  For wider compatibility, install Python from python.org and re-run with:"
    echo "  PYTHON_BIN=/Library/Frameworks/Python.framework/Versions/3.X/bin/python3 ./scripts/build_dmg.sh"
fi

TARGET_TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
[[ -n "$TARGET_TRIPLE" ]] || fail "Could not determine Rust host target."
echo "Target  : $TARGET_TRIPLE"

# ------------------------------------------------------------
step "Setting up Python build environment ($VENV_DIR)"
# ------------------------------------------------------------
cd "$PROJECT_ROOT"
[[ -d "$VENV_DIR" ]] || "$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt
success "Python dependencies installed"

# ------------------------------------------------------------
step "Building Python backend (PyInstaller)"
# ------------------------------------------------------------
# Keep unrelated library search paths out of the frozen binary.
unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH || true

rm -rf "$PROJECT_ROOT/build" "$PROJECT_ROOT/dist"
python -m PyInstaller --clean --noconfirm backend.spec

BACKEND_BINARY="$PROJECT_ROOT/dist/backend"
[[ -f "$BACKEND_BINARY" ]] || fail "PyInstaller did not create dist/backend."
success "Backend built: $BACKEND_BINARY"

# ------------------------------------------------------------
step "Smoke-testing backend on http://127.0.0.1:8001"
# ------------------------------------------------------------
if lsof -iTCP:8001 -sTCP:LISTEN >/dev/null 2>&1; then
    fail "Port 8001 is already in use. Quit any running Alfred/backend and try again."
fi

BACKEND_LOG="$PROJECT_ROOT/build/backend-smoke-test.log"
"$BACKEND_BINARY" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
BACKEND_OK=false
for _ in {1..40}; do
    kill -0 "$BACKEND_PID" 2>/dev/null || break
    if curl -fsS "http://127.0.0.1:8001/" >/dev/null 2>&1; then BACKEND_OK=true; break; fi
    sleep 0.5
done
kill "$BACKEND_PID" 2>/dev/null || true
wait "$BACKEND_PID" 2>/dev/null || true

if [[ "$BACKEND_OK" != true ]]; then
    echo "----- backend output -----"; cat "$BACKEND_LOG" || true; echo "--------------------------"
    fail "Frozen backend did not start."
fi
success "Backend smoke test passed"

deactivate || true

# ------------------------------------------------------------
step "Preparing Tauri sidecar"
# ------------------------------------------------------------
SIDECAR_DIR="$TAURI_SRC/binaries"
mkdir -p "$SIDECAR_DIR"
cp "$BACKEND_BINARY" "$SIDECAR_DIR/backend-$TARGET_TRIPLE"
chmod +x "$SIDECAR_DIR/backend-$TARGET_TRIPLE"
success "Sidecar: $SIDECAR_DIR/backend-$TARGET_TRIPLE"

# ------------------------------------------------------------
step "Installing Node dependencies"
# ------------------------------------------------------------
cd "$TAURI_DIR"
if [[ -f package-lock.json ]]; then npm ci; else npm install; fi

# ------------------------------------------------------------
step "Building .app and .dmg (ad-hoc signed)"
# ------------------------------------------------------------
# signingIdentity "-" = ad-hoc signature: no Apple account needed,
# required for the app to run on Apple Silicon.
# CI=true (the default here) makes Tauri pass --skip-jenkins to
# bundle_dmg.sh, skipping the AppleScript that drives Finder to lay out
# the DMG window. That step needs the "Terminal -> Finder" Automation
# permission, which can't be granted remotely (error -1743). The DMG
# still contains the .app and the Applications link; only the window
# layout is skipped. Run with CI=false (after allowing Terminal to
# control Finder) for the laid-out window. CI is unset in that case,
# since some tools only check whether CI is set, not its value.
if [[ "${CI:-true}" == "false" ]]; then unset CI; else export CI=true; fi
npm run tauri build -- \
    --bundles app,dmg \
    --config '{"bundle":{"macOS":{"signingIdentity":"-"}}}'

# ------------------------------------------------------------
step "Result"
# ------------------------------------------------------------
BUNDLE_DIR="$TAURI_SRC/target/release/bundle"
APP_PATH="$(find "$BUNDLE_DIR/macos" -maxdepth 1 -name '*.app' -type d | head -n 1)"
DMG_PATH="$(find "$BUNDLE_DIR/dmg" -maxdepth 1 -name '*.dmg' -type f | head -n 1)"

[[ -n "$DMG_PATH" ]] || fail "No .dmg found under $BUNDLE_DIR/dmg"

echo "App : $APP_PATH"
echo "DMG : $DMG_PATH ($(du -h "$DMG_PATH" | cut -f1))"
echo
echo "Signature check:"
codesign --verify --deep --strict --verbose=1 "$APP_PATH" 2>&1 | sed 's/^/  /' || true
codesign -dv "$APP_PATH" 2>&1 | grep -E 'Identifier|Signature|TeamIdentifier' | sed 's/^/  /' || true
echo
echo "Architecture:"
find "$APP_PATH/Contents/MacOS" -type f -perm -u+x -exec file {} \; | sed 's/^/  /'
echo
success "Done. Open the DMG to test drag-to-install:"
echo "  open \"$DMG_PATH\""
