#!/bin/bash
#
# ZDTT Terminal Installer
# Installs ZDTT Terminal and sets up the zdtt command
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
if [ ! -f /etc/debian_version ]; then
    echo -e "${RED}Error: ZDTT Terminal only works on Debian-based Linux systems.${NC}"
    echo "This does not appear to be a Debian-based distribution."
    echo ""
    echo "Press any key to exit..."
    read -n 1 -s -r
    exit 1
fi

echo -e "${GREEN}✓${NC} Debian-based Linux detected"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed"
    echo ""
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
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✓${NC} Python 3 is already installed: ${PYTHON_VERSION}"
fi

echo ""

# Create directories if they don't exist
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

echo "Installing ZDTT Terminal..."

# Copy the terminal.py and install.sh to the installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/terminal.py" "$INSTALL_DIR/terminal.py"
cp "$SCRIPT_DIR/install.sh" "$INSTALL_DIR/install.sh"
chmod +x "$INSTALL_DIR/terminal.py"
chmod +x "$INSTALL_DIR/install.sh"

echo -e "${GREEN}✓${NC} ZDTT Terminal files copied to $INSTALL_DIR"

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
        echo "ZDTT Terminal v0.0.1.alpha"
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

