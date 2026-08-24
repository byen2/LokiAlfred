#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAURI_DIR="$PROJECT_ROOT/Alfred"
TAURI_SRC="$TAURI_DIR/src-tauri"
VENV_DIR="$PROJECT_ROOT/.venv"

echo "======================================"
echo "        Loki Alfred Installer"
echo "======================================"
echo

ask_yes_no() {
    local prompt="$1"
    local default="${2:-Y}"

    if [[ "$default" == "Y" ]]; then
        read -r -p "$prompt [Y/n] " reply
        reply="${reply:-Y}"
    else
        read -r -p "$prompt [y/N] " reply
        reply="${reply:-N}"
    fi

    [[ "$reply" =~ ^[Yy]$ ]]
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "Project root: $PROJECT_ROOT"
echo

# ============================================================
# macOS check
# ============================================================

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Error: This installer currently supports macOS only."
    exit 1
fi

echo "✓ macOS detected"

# ============================================================
# Xcode Command Line Tools
# ============================================================

if ! xcode-select -p >/dev/null 2>&1; then
    echo
    echo "Xcode Command Line Tools are required."

    if ask_yes_no "Install Xcode Command Line Tools now?"; then
        xcode-select --install || true

        echo
        echo "Complete the Apple installation dialog, then run install.sh again."
        exit 0
    else
        echo "Cannot continue without Xcode Command Line Tools."
        exit 1
    fi
fi

echo "✓ Xcode Command Line Tools found"

# ============================================================
# Homebrew
# ============================================================

if ! command_exists brew; then
    echo
    echo "Homebrew was not found."

    if ask_yes_no "Install Homebrew?"; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Apple Silicon
        if [[ -x "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    else
        echo "Homebrew is required for automatic dependency installation."
        exit 1
    fi
fi

echo "✓ Homebrew found"

# ============================================================
# Optional Recoll
# ============================================================

if command_exists recoll; then
    echo "✓ Recoll found"
else
    echo
    echo "Recoll is not installed."

    if ask_yes_no "Install Recoll now?"; then
        brew install recoll
    else
        echo "Skipping Recoll."
        echo "Alfred's search functionality may not work until Recoll is installed."
    fi
fi

# ============================================================
# Optional Ollama
# ============================================================

if command_exists ollama; then
    echo "✓ Ollama found"
else
    echo
    echo "Ollama is not installed."

    if ask_yes_no "Install Ollama now?"; then
        brew install --cask ollama
    else
        echo "Skipping Ollama."
        echo "LLM chat will not work until Ollama is installed."
    fi
fi

# ============================================================
# Python
# ============================================================

if ! command_exists python3; then
    echo
    echo "Installing Python..."
    brew install python
fi

echo "✓ Python found: $(python3 --version)"

# ============================================================
# Node.js
# ============================================================

if ! command_exists node || ! command_exists npm; then
    echo
    echo "Installing Node.js..."
    brew install node
fi

echo "✓ Node found: $(node --version)"
echo "✓ npm found: $(npm --version)"

# ============================================================
# Rust
# ============================================================

if ! command_exists cargo || ! command_exists rustc; then
    echo
    echo "Rust is not installed."

    if ask_yes_no "Install Rust using rustup?"; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

        if [[ -f "$HOME/.cargo/env" ]]; then
            source "$HOME/.cargo/env"
        fi
    else
        echo "Rust is required to build Alfred."
        exit 1
    fi
fi

echo "✓ Rust found: $(rustc --version)"
echo "✓ Cargo found: $(cargo --version)"

# ============================================================
# Verify project files
# ============================================================

if [[ ! -d "$TAURI_DIR" ]]; then
    echo "Error: Alfred directory not found:"
    echo "$TAURI_DIR"
    exit 1
fi

if [[ ! -f "$TAURI_SRC/Cargo.toml" ]]; then
    echo "Error: Cargo.toml not found:"
    echo "$TAURI_SRC/Cargo.toml"
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/backend.py" ]]; then
    echo "Error: backend.py not found."
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/requirements.txt" ]]; then
    echo "Error: requirements.txt not found."
    exit 1
fi

# ============================================================
# Python virtual environment
# ============================================================

echo
echo "Setting up Python environment..."

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_ROOT/requirements.txt"

if ! python -m PyInstaller --version >/dev/null 2>&1; then
    python -m pip install pyinstaller
fi

echo "✓ Python environment ready"

# ============================================================
# Build backend
# ============================================================

echo
echo "Building Python backend..."

cd "$PROJECT_ROOT"

rm -rf "$PROJECT_ROOT/build"
rm -rf "$PROJECT_ROOT/dist"

if [[ -f "$PROJECT_ROOT/backend.spec" ]]; then
    python -m PyInstaller --noconfirm --clean "$PROJECT_ROOT/backend.spec"
else
    PYINSTALLER_ARGS=(
        --noconfirm
        --clean
        --onefile
        --name backend
    )

    if [[ -d "$PROJECT_ROOT/templates" ]]; then
        PYINSTALLER_ARGS+=(--add-data "$PROJECT_ROOT/templates:templates")
    fi

    if [[ -d "$PROJECT_ROOT/static" ]]; then
        PYINSTALLER_ARGS+=(--add-data "$PROJECT_ROOT/static:static")
    fi

    if [[ -f "$PROJECT_ROOT/ml_passages.txt" ]]; then
        PYINSTALLER_ARGS+=(--add-data "$PROJECT_ROOT/ml_passages.txt:.")
    fi

    PYINSTALLER_ARGS+=("$PROJECT_ROOT/backend.py")

    python -m PyInstaller "${PYINSTALLER_ARGS[@]}"
fi

BACKEND_BINARY="$PROJECT_ROOT/dist/backend"

if [[ ! -f "$BACKEND_BINARY" ]]; then
    echo "Error: PyInstaller did not create:"
    echo "$BACKEND_BINARY"
    exit 1
fi

echo "✓ Backend built"

# ============================================================
# Copy backend as Tauri sidecar
# ============================================================

TARGET_TRIPLE="$(rustc --print host-tuple)"

echo
echo "Rust target: $TARGET_TRIPLE"

mkdir -p "$TAURI_SRC/binaries"

TAURI_BACKEND="$TAURI_SRC/binaries/backend-$TARGET_TRIPLE"

cp "$BACKEND_BINARY" "$TAURI_BACKEND"
chmod +x "$TAURI_BACKEND"

echo "✓ Backend sidecar prepared"
echo "  $TAURI_BACKEND"

# ============================================================
# Install Node dependencies
# ============================================================

echo
echo "Installing frontend dependencies..."

cd "$TAURI_DIR"

if [[ -f "package-lock.json" ]]; then
    npm ci
else
    npm install
fi

echo "✓ Frontend dependencies installed"

# ============================================================
# Cargo check
# ============================================================

echo
echo "Checking Rust/Tauri configuration..."

cd "$TAURI_SRC"
cargo check

echo "✓ Cargo check passed"

# ============================================================
# Build application
# ============================================================

echo
echo "Building Loki Alfred..."

cd "$TAURI_DIR"
npm run tauri build -- --bundles app

# ============================================================
# Find built app
# ============================================================

APP_BUNDLE_DIR="$TAURI_SRC/target/release/bundle/macos"

APP_PATH=""

if [[ -d "$APP_BUNDLE_DIR" ]]; then
    APP_PATH="$(find "$APP_BUNDLE_DIR" -maxdepth 1 -name "*.app" -type d | head -n 1)"
fi

echo
echo "======================================"
echo "          Setup Complete"
echo "======================================"
echo

if [[ -n "$APP_PATH" ]]; then
    echo "Alfred was built successfully:"
    echo
    echo "$APP_PATH"
    echo

    if ask_yes_no "Launch Alfred now?"; then
        open "$APP_PATH"
    fi
else
    echo "Build completed, but the .app could not be located automatically."
    echo
    echo "Check:"
    echo "$TAURI_SRC/target/release/bundle/"
fi

# ============================================================
# Optional Ollama model
# ============================================================

if command_exists ollama; then
    echo

    if ask_yes_no "Would you like to install a starter Ollama model?" "N"; then
        read -r -p "Model name [llama3.2]: " MODEL_NAME
        MODEL_NAME="${MODEL_NAME:-llama3.2}"

        echo "Installing Ollama model: $MODEL_NAME"
        ollama pull "$MODEL_NAME"
    fi
fi

echo
echo "Important:"
echo "  • Ollama must be running for AI chat."
echo "  • At least one Ollama model must be installed."
echo "  • Recoll must have an index configured for search."
echo
echo "Done."