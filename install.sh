#!/bin/bash
#
# ZDTT Terminal Installer
# Downloads and installs ZDTT Terminal from zdtt-sources.zane.org
#
# Quick Install:
#   curl -O https://zdtt-sources.zane.org/install.sh && chmod +x install.sh && ./install.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "  ZDTT Terminal Installation Script"
echo "========================================="
echo ""

# Installation directories
INSTALL_DIR="$HOME/.local/share/zdtt"
BIN_DIR="$HOME/.local/bin"

# Check if ZDTT is already installed
if [ -f "$BIN_DIR/zdtt" ] || [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}ZDTT Terminal is already installed!${NC}"
    echo ""
    echo "What would you like to do?"
    echo "  1) Reinstall ZDTT Terminal"
    echo "  2) Uninstall ZDTT Terminal"
    echo "  3) Cancel"
    echo ""
    read -p "Enter your choice (1-3): " -n 1 -r
    echo ""
    echo ""
    
    case $REPLY in
        1)
            echo "Reinstalling ZDTT Terminal..."
            echo ""
            # Don't remove the directory if we're running from it
            # Just overwrite the files instead
            ;;
        2)
            echo "Uninstalling ZDTT Terminal..."
            rm -rf "$INSTALL_DIR"
            rm -f "$BIN_DIR/zdtt"
            echo ""
            echo -e "${GREEN}✓${NC} ZDTT Terminal has been uninstalled successfully."
            echo ""
            echo "Press any key to exit..."
            read -n 1 -s -r
            exit 0
            ;;
        3)
            echo "Installation cancelled."
            echo ""
            echo "Press any key to exit..."
            read -n 1 -s -r
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice.${NC} Installation cancelled."
            echo ""
            echo "Press any key to exit..."
            read -n 1 -s -r
            exit 1
            ;;
    esac
fi

# Check if running on Debian-based Linux
IS_DEBIAN=false
if [ -f /etc/debian_version ]; then
    IS_DEBIAN=true
    echo -e "${GREEN}✓${NC} Debian-based Linux detected"
else
    echo -e "${YELLOW}⚠${NC}  Non-Debian distribution detected"
    echo ""
    echo "ZDTT Terminal is optimized for Debian-based systems."
    echo "(Debian, Ubuntu, Linux Mint, Pop!_OS, etc.)"
    echo ""
    echo "Running on a non-Debian system may result in:"
    echo "  • Some commands may not work as expected"
    echo "  • Auto-install features (like neofetch) will not work"
    echo "  • Reduced plugin compatibility"
    echo "  • Package management commands unavailable"
    echo ""
    read -p "Continue installation anyway? (yes/no): " -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Installation cancelled."
        echo ""
        echo "Press any key to exit..."
        read -n 1 -s -r
        exit 0
    fi
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed"
    echo ""
    
    if [ "$IS_DEBIAN" = true ]; then
        echo "Installing Python 3..."
        
        # Update package list and install Python 3
        sudo apt-get update
        sudo apt-get install -y python3
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install Python 3${NC}"
            echo "Please install Python 3 manually: sudo apt-get install python3"
            echo ""
            echo "Press any key to exit..."
            read -n 1 -s -r
            exit 1
        fi
        
        echo -e "${GREEN}✓${NC} Python 3 installed successfully"
    else
        echo -e "${RED}Python 3 is required but auto-install is not supported on non-Debian systems.${NC}"
        echo ""
        echo "Please install Python 3 manually using your package manager:"
        echo "  • Arch/Manjaro: sudo pacman -S python"
        echo "  • Fedora: sudo dnf install python3"
        echo "  • openSUSE: sudo zypper install python3"
        echo ""
        echo "Press any key to exit..."
        read -n 1 -s -r
        exit 1
    fi
else
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓${NC} Python 3 is already installed: ${PYTHON_VERSION}"
fi

echo ""

# Create directories if they don't exist
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$HOME/.zdtt/plugins"

echo "Installing ZDTT Terminal..."
echo "Downloading files from zdtt-sources.zane.org..."
echo ""

# Base URL for ZDTT sources
BASE_URL="https://zdtt-sources.zane.org"

# Files to download
declare -a FILES=("terminal.py" "version.txt")

# Download files
DOWNLOAD_SUCCESS=true

for file in "${FILES[@]}"; do
    echo "Downloading $file..."
    
    if command -v wget &> /dev/null; then
        if wget -q "$BASE_URL/$file" -O "$INSTALL_DIR/$file" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $file downloaded"
        else
            echo -e "${RED}✗${NC} Failed to download $file"
            DOWNLOAD_SUCCESS=false
            break
        fi
    elif command -v curl &> /dev/null; then
        if curl -sSL "$BASE_URL/$file" -o "$INSTALL_DIR/$file" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $file downloaded"
        else
            echo -e "${RED}✗${NC} Failed to download $file"
            DOWNLOAD_SUCCESS=false
            break
        fi
    else
        echo -e "${RED}✗${NC} Neither wget nor curl found"
        echo "Please install wget or curl to proceed"
        echo ""
        echo "Press any key to exit..."
        read -n 1 -s -r
        exit 1
    fi
done

if [ "$DOWNLOAD_SUCCESS" = false ]; then
    echo ""
    echo -e "${RED}Installation failed - unable to download required files${NC}"
    echo "Please check your internet connection and try again."
    echo ""
    echo "Press any key to exit..."
    read -n 1 -s -r
    exit 1
fi

# Copy this installer to the installation directory for future use
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$0" "$INSTALL_DIR/install.sh"

# Set executable permissions
chmod +x "$INSTALL_DIR/terminal.py"
chmod +x "$INSTALL_DIR/install.sh"

echo ""
echo -e "${GREEN}✓${NC} ZDTT Terminal files installed to $INSTALL_DIR"

# Download and install example plugin
echo ""
echo "Installing example plugin..."
EXAMPLE_PLUGIN_URL="https://plugins.zane.org/example_plugin.py"
PLUGIN_DEST="$HOME/.zdtt/plugins/example_plugin.py"

# Try wget first (more reliable), then curl
PLUGIN_DOWNLOADED=false

if command -v wget &> /dev/null; then
    if wget -q "$EXAMPLE_PLUGIN_URL" -O "$PLUGIN_DEST" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Example plugin installed from plugins.zane.org"
        PLUGIN_DOWNLOADED=true
    fi
fi

if [ "$PLUGIN_DOWNLOADED" = false ] && command -v curl &> /dev/null; then
    # Suppress curl snap warnings and try download
    if curl -sSL "$EXAMPLE_PLUGIN_URL" -o "$PLUGIN_DEST" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Example plugin installed from plugins.zane.org"
        PLUGIN_DOWNLOADED=true
    fi
fi

if [ "$PLUGIN_DOWNLOADED" = false ]; then
    echo -e "${YELLOW}⚠${NC}  Could not download example plugin"
    echo "   You can install it later with: zps install $EXAMPLE_PLUGIN_URL"
    # Don't exit - continue with installation
fi

# Create the zdtt wrapper script
cat > "$BIN_DIR/zdtt" << 'EOF'
#!/bin/bash
#
# ZDTT Terminal Wrapper
#

ZDTT_DIR="$HOME/.local/share/zdtt"

case "$1" in
    start)
        # Clear screen before starting ZDTT
        clear
        python3 "$ZDTT_DIR/terminal.py"
        ;;
    update)
        echo "Checking for updates..."
        
        # Get current version
        if [ -f "$ZDTT_DIR/version.txt" ]; then
            CURRENT_VERSION=$(cat "$ZDTT_DIR/version.txt")
        else
            CURRENT_VERSION="unknown"
        fi
        
        # Get remote version
        if command -v curl &> /dev/null; then
            REMOTE_VERSION=$(curl -sSL https://zdtt-sources.zane.org/version.txt 2>/dev/null)
        elif command -v wget &> /dev/null; then
            REMOTE_VERSION=$(wget -qO- https://zdtt-sources.zane.org/version.txt 2>/dev/null)
        else
            echo "Error: Neither curl nor wget found"
            exit 1
        fi
        
        if [ -z "$REMOTE_VERSION" ]; then
            echo "Error: Could not fetch remote version"
            exit 1
        fi
        
        echo "Current version: $CURRENT_VERSION"
        echo "Latest version:  $REMOTE_VERSION"
        echo ""
        
        if [ "$CURRENT_VERSION" = "$REMOTE_VERSION" ]; then
            echo "✓ You're already running the latest version!"
        else
            echo "Update available!"
            read -p "Do you want to update now? (yes/no): " -r
            if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                # Run the installer
                if [ -f "$ZDTT_DIR/install.sh" ]; then
                    bash "$ZDTT_DIR/install.sh"
                else
                    echo "Downloading installer..."
                    TEMP_INSTALLER="/tmp/zdtt_install.sh"
                    if command -v curl &> /dev/null; then
                        curl -sSL https://zdtt-sources.zane.org/install.sh -o "$TEMP_INSTALLER"
                    else
                        wget -qO "$TEMP_INSTALLER" https://zdtt-sources.zane.org/install.sh
                    fi
                    bash "$TEMP_INSTALLER"
                    rm -f "$TEMP_INSTALLER"
                fi
            else
                echo "Update cancelled."
            fi
        fi
        ;;
    installer|install|reinstall)
        # Run the installer for reinstalling/updating
        if [ -f "$ZDTT_DIR/install.sh" ]; then
            bash "$ZDTT_DIR/install.sh"
        else
            echo "Error: Installer not found at $ZDTT_DIR/install.sh"
            echo "Please download the installer from the ZDTT repository."
            exit 1
        fi
        ;;
    uninstall)
        echo "Uninstalling ZDTT Terminal..."
        rm -rf "$ZDTT_DIR"
        rm -f "$HOME/.local/bin/zdtt"
        echo "ZDTT Terminal has been uninstalled."
        ;;
    version)
        if [ -f "$ZDTT_DIR/version.txt" ]; then
            VERSION=$(cat "$ZDTT_DIR/version.txt")
            echo "ZDTT Terminal v$VERSION"
        else
            echo "ZDTT Terminal v0.0.1.a"
        fi
        echo ""
        echo "Features:"
        echo "  • Command history (↑/↓ navigation)"
        echo "  • Tab completion"
        echo "  • Colorized prompt"
        echo "  • Plugin system"
        echo "  • Native command support"
        ;;
    *)
        echo "ZDTT Terminal"
        echo ""
        echo "Usage:"
        echo "  zdtt start        - Start the ZDTT Terminal"
        echo "  zdtt update       - Check for and install updates"
        echo "  zdtt installer    - Run installer (for updates/reinstall)"
        echo "  zdtt version      - Display version information"
        echo "  zdtt uninstall    - Uninstall ZDTT Terminal"
        echo ""
        ;;
esac
EOF

chmod +x "$BIN_DIR/zdtt"

echo -e "${GREEN}✓${NC} ZDTT command installed to $BIN_DIR"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo -e "${YELLOW}Warning: $HOME/.local/bin is not in your PATH${NC}"
    echo ""
    echo "To use the 'zdtt' command, add the following line to your ~/.bashrc:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run: source ~/.bashrc"
    echo ""
    
    # Ask if user wants to add it automatically
    read -p "Would you like to add it to your ~/.bashrc now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "" >> "$HOME/.bashrc"
        echo "# Added by ZDTT Terminal installer" >> "$HOME/.bashrc"
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$HOME/.bashrc"
        echo -e "${GREEN}✓${NC} Added to ~/.bashrc"
        echo "Please run: source ~/.bashrc"
    fi
else
    echo -e "${GREEN}✓${NC} ~/.local/bin is already in your PATH"
fi

echo ""
echo "========================================="
echo -e "${GREEN}Installation complete!${NC}"
echo "========================================="
echo ""
echo "To start ZDTT Terminal, run:"
echo "  zdtt start"
echo ""
echo "Press any key to exit..."
read -n 1 -s -r

