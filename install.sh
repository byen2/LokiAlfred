#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# Loki Alfred macOS installer
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAURI_DIR="$PROJECT_ROOT/Alfred"
TAURI_SRC="$TAURI_DIR/src-tauri"
VENV_DIR="$PROJECT_ROOT/.venv"

echo
echo "================================================"
echo "             Loki Alfred Installer"
echo "================================================"
echo

# ============================================================
# Helpers
# ============================================================

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-Y}"
    local reply

    if [[ "$default" == "Y" ]]; then
        read -r -p "$prompt [Y/n] " reply
        reply="${reply:-Y}"
    else
        read -r -p "$prompt [y/N] " reply
        reply="${reply:-N}"
    fi

    [[ "$reply" =~ ^[Yy]$ ]]
}

success() {
    echo "✓ $1"
}

warning() {
    echo "⚠ $1"
}

fail() {
    echo
    echo "ERROR: $1"
    echo
    exit 1
}

# ============================================================
# macOS check
# ============================================================

if [[ "$(uname -s)" != "Darwin" ]]; then
    fail "This installer currently supports macOS only."
fi

success "macOS detected"

# ============================================================
# Verify project structure
# ============================================================

[[ -d "$TAURI_DIR" ]] \
    || fail "Could not find Alfred directory at: $TAURI_DIR"

[[ -d "$TAURI_SRC" ]] \
    || fail "Could not find src-tauri at: $TAURI_SRC"

[[ -f "$TAURI_SRC/Cargo.toml" ]] \
    || fail "Could not find Alfred/src-tauri/Cargo.toml"

[[ -f "$TAURI_SRC/tauri.conf.json" ]] \
    || fail "Could not find Alfred/src-tauri/tauri.conf.json"

[[ -f "$PROJECT_ROOT/backend.py" ]] \
    || fail "Could not find backend.py"

[[ -f "$PROJECT_ROOT/backend.spec" ]] \
    || fail "Could not find backend.spec"

[[ -f "$PROJECT_ROOT/requirements.txt" ]] \
    || fail "Could not find requirements.txt"

success "Project files found"

# ============================================================
# Xcode Command Line Tools
# ============================================================

if ! xcode-select -p >/dev/null 2>&1; then
    echo
    echo "Xcode Command Line Tools are required to compile Alfred."

    if ask_yes_no "Install Xcode Command Line Tools now?"; then
        xcode-select --install || true

        echo
        echo "A macOS installation window should have appeared."
        echo "Finish installing the Command Line Tools and then"
        echo "run ./install.sh again."
        exit 0
    else
        fail "Xcode Command Line Tools are required."
    fi
fi

success "Xcode Command Line Tools found"

# ============================================================
# Homebrew
# ============================================================

if ! command_exists brew; then
    echo
    echo "Homebrew is not installed."
    echo "Alfred can use Homebrew to install missing dependencies."

    if ask_yes_no "Would you like to install Homebrew?"; then

        /bin/bash -c \
        "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Apple Silicon Homebrew
        if [[ -x "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi

        # Intel Homebrew
        if [[ -x "/usr/local/bin/brew" ]] && ! command_exists brew; then
            export PATH="/usr/local/bin:$PATH"
        fi

    else
        warning "Homebrew installation skipped."
        echo "Missing dependencies will need to be installed manually."
    fi
fi

if command_exists brew; then
    success "Homebrew found"
fi

# ============================================================
# Python
# ============================================================

if ! command_exists python3; then

    echo
    echo "Python 3 was not found."

    if command_exists brew; then
        echo "Installing Python..."
        brew install python
    else
        fail "Python 3 is required. Install Python and run this installer again."
    fi

fi

success "Python: $(python3 --version)"

# ============================================================
# Node.js / npm
# ============================================================

if ! command_exists node || ! command_exists npm; then

    echo
    echo "Node.js/npm were not found."

    if command_exists brew; then
        echo "Installing Node.js..."
        brew install node
    else
        fail "Node.js is required. Install Node.js and run this installer again."
    fi

fi

success "Node: $(node --version)"
success "npm: $(npm --version)"

# ============================================================
# Rust / Cargo
# ============================================================

if ! command_exists rustc || ! command_exists cargo; then

    echo
    echo "Rust is required to build the Tauri application."

    if ask_yes_no "Would you like to install Rust using rustup?"; then

        curl --proto '=https' \
             --tlsv1.2 \
             -sSf \
             https://sh.rustup.rs \
             | sh -s -- -y

        if [[ -f "$HOME/.cargo/env" ]]; then
            # shellcheck disable=SC1090
            source "$HOME/.cargo/env"
        fi

    else
        fail "Rust is required to build Alfred."
    fi
fi

success "Rust: $(rustc --version)"
success "Cargo: $(cargo --version)"

# ============================================================
# Recoll - optional
# ============================================================

echo

RECOLL_FOUND=false

if command_exists recoll || \
   command_exists recollindex || \
   [[ -d "/Applications/Recoll.app" ]]; then

    RECOLL_FOUND=true
    success "Recoll found"

else

    echo "Recoll was not detected."
    echo "Recoll provides Alfred's local document search."

    if ask_yes_no "Would you like to install Recoll now?"; then

        if command_exists brew; then

            echo
            echo "Attempting to install Recoll with Homebrew..."

            if brew install --cask recoll; then
                RECOLL_FOUND=true
                success "Recoll installed"
            else
                warning "Homebrew could not install Recoll automatically."
                echo
                echo "Please install Recoll manually from:"
                echo "https://www.recoll.org/"
            fi

        else
            warning "Homebrew is not available."
            echo
            echo "Install Recoll manually from:"
            echo "https://www.recoll.org/"
        fi

    else
        warning "Recoll installation skipped."
        echo "Document search will not work until Recoll is installed."
    fi
fi

# ============================================================
# Ollama - optional
# ============================================================

echo

OLLAMA_FOUND=false

if command_exists ollama || \
   [[ -d "/Applications/Ollama.app" ]]; then

    OLLAMA_FOUND=true
    success "Ollama found"

else

    echo "Ollama was not detected."
    echo "Ollama provides Alfred's local language models."

    if ask_yes_no "Would you like to install Ollama now?"; then

        if command_exists brew; then

            echo
            echo "Installing Ollama..."

            if brew install --cask ollama; then
                OLLAMA_FOUND=true
                success "Ollama installed"
            else
                warning "Automatic Ollama installation failed."
                echo
                echo "Install Ollama manually from:"
                echo "https://ollama.com/"
            fi

        else
            warning "Homebrew is unavailable."
            echo
            echo "Install Ollama manually from:"
            echo "https://ollama.com/"
        fi

    else
        warning "Ollama installation skipped."
        echo "AI chat will not work until Ollama is installed."
    fi
fi

# Refresh shell path after optional installations.

hash -r 2>/dev/null || true

if command_exists ollama; then
    OLLAMA_FOUND=true
fi

# ============================================================
# Optional Ollama model
# ============================================================

if [[ "$OLLAMA_FOUND" == true ]]; then

    echo

    # Launch Ollama.app if available so the local service can start.
    if [[ -d "/Applications/Ollama.app" ]]; then
        open -a Ollama >/dev/null 2>&1 || true
        sleep 2
    fi

    if command_exists ollama; then

        echo "Installed Ollama models:"
        echo

        ollama list || true

        echo

        if ask_yes_no \
            "Would you like to download a starter Ollama model?" \
            "N"; then

            read -r -p "Model name [llama3.2]: " MODEL_NAME
            MODEL_NAME="${MODEL_NAME:-llama3.2}"

            echo
            echo "Downloading Ollama model: $MODEL_NAME"
            echo "This may take some time depending on model size."
            echo

            ollama pull "$MODEL_NAME"

            success "Model installed: $MODEL_NAME"
        fi

    fi

fi

# ============================================================
# Python virtual environment
# ============================================================

echo
echo "------------------------------------------------"
echo "Setting up Python environment"
echo "------------------------------------------------"
echo

cd "$PROJECT_ROOT"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

success "Virtual environment active"

echo
echo "Updating pip..."

python -m pip install --upgrade pip

echo
echo "Installing Python requirements..."

python -m pip install -r "$PROJECT_ROOT/requirements.txt"

# Ensure PyInstaller exists even if the requirements file changes later.

if ! python -m PyInstaller --version >/dev/null 2>&1; then
    echo
    echo "Installing PyInstaller..."
    python -m pip install pyinstaller
fi

success "Python dependencies installed"

# ============================================================
# Build Python backend
# ============================================================

echo
echo "------------------------------------------------"
echo "Building Alfred backend"
echo "------------------------------------------------"
echo

cd "$PROJECT_ROOT"

rm -rf "$PROJECT_ROOT/build"
rm -rf "$PROJECT_ROOT/dist"

python -m PyInstaller \
    --clean \
    --noconfirm \
    "$PROJECT_ROOT/backend.spec"

BACKEND_BINARY="$PROJECT_ROOT/dist/backend"

if [[ ! -f "$BACKEND_BINARY" ]]; then
    fail "PyInstaller did not create dist/backend."
fi

chmod +x "$BACKEND_BINARY"

success "Python backend built"

# ============================================================
# Determine Rust target
# ============================================================

TARGET_TRIPLE="$(rustc --print host-tuple)"

echo
echo "Detected architecture:"
echo "$TARGET_TRIPLE"
echo

# ============================================================
# Prepare Tauri sidecar
# ============================================================

SIDECAR_DIR="$TAURI_SRC/binaries"
SIDECAR_PATH="$SIDECAR_DIR/backend-$TARGET_TRIPLE"

mkdir -p "$SIDECAR_DIR"

cp "$BACKEND_BINARY" "$SIDECAR_PATH"

chmod +x "$SIDECAR_PATH"

success "Backend sidecar prepared"
echo "  $SIDECAR_PATH"

# ============================================================
# Install JavaScript dependencies
# ============================================================

echo
echo "------------------------------------------------"
echo "Installing Tauri / Node dependencies"
echo "------------------------------------------------"
echo

cd "$TAURI_DIR"

if [[ -f "$TAURI_DIR/package-lock.json" ]]; then
    npm ci
else
    npm install
fi

success "Node dependencies installed"

# ============================================================
# Verify Rust project
# ============================================================

echo
echo "------------------------------------------------"
echo "Checking Rust/Tauri project"
echo "------------------------------------------------"
echo

cd "$TAURI_SRC"

cargo check

success "Cargo check passed"

# ============================================================
# Build Tauri app
# ============================================================

echo
echo "------------------------------------------------"
echo "Building Loki Alfred"
echo "------------------------------------------------"
echo

cd "$TAURI_DIR"

npm run tauri build -- --bundles app

# ============================================================
# Locate application
# ============================================================

APP_BUNDLE_DIR="$TAURI_SRC/target/release/bundle/macos"

APP_PATH=""

if [[ -d "$APP_BUNDLE_DIR" ]]; then
    APP_PATH="$(
        find "$APP_BUNDLE_DIR" \
            -maxdepth 1 \
            -type d \
            -name "*.app" \
            | head -n 1
    )"
fi

# ============================================================
# Installation summary
# ============================================================

echo
echo "================================================"
echo "              Installation Complete"
echo "================================================"
echo

success "Python environment configured"
success "Backend built"
success "Tauri application built"

if [[ "$RECOLL_FOUND" == true ]]; then
    success "Recoll detected"
else
    warning "Recoll is not currently available"
fi

if [[ "$OLLAMA_FOUND" == true ]]; then
    success "Ollama detected"
else
    warning "Ollama is not currently available"
fi

echo

if [[ -n "$APP_PATH" && -d "$APP_PATH" ]]; then

    echo "Alfred was built here:"
    echo
    echo "  $APP_PATH"
    echo

    if ask_yes_no "Would you like to launch Alfred now?"; then
        open "$APP_PATH"
    fi

else

    warning "The build completed but the .app could not be located automatically."

    echo
    echo "Look inside:"
    echo
    echo "  $TAURI_SRC/target/release/bundle/"
fi

# ============================================================
# Recoll reminder
# ============================================================

echo
echo "------------------------------------------------"
echo "Before using Alfred"
echo "------------------------------------------------"
echo

if [[ "$RECOLL_FOUND" == true ]]; then
    echo "Recoll:"
    echo "  1. Open Recoll."
    echo "  2. Select the folders/documents you want indexed."
    echo "  3. Build or update the Recoll index."
else
    echo "Recoll:"
    echo "  Install Recoll before using Alfred's document search."
fi

echo

if [[ "$OLLAMA_FOUND" == true ]]; then
    echo "Ollama:"
    echo "  Make sure Ollama is running and at least one model"
    echo "  is installed."
    echo
    echo "  View models with:"
    echo "      ollama list"
    echo
    echo "  Download a model with:"
    echo "      ollama pull llama3.2"
else
    echo "Ollama:"
    echo "  Install Ollama before using Alfred's AI features."
fi

echo
echo "================================================"
echo "                  Done!"
echo "================================================"
echo