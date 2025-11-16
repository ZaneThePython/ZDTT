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

# Check if running on macOS
IS_MAC=false
if [[ "$(uname)" == "Darwin" ]]; then
    IS_MAC=true
    DETECTED_DISTRO="mac"
    echo -e "${GREEN}✓${NC} macOS detected"
fi

# Check if running on a supported Linux distribution
IS_DEBIAN=false
IS_ARCH=false
if [ "$IS_MAC" = false ]; then
    DETECTED_DISTRO="other"
fi

OS_ID=""
OS_LIKE=""
if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_ID=$(echo "${ID:-}" | tr '[:upper:]' '[:lower:]')
    OS_LIKE=$(echo "${ID_LIKE:-}" | tr '[:upper:]' '[:lower:]')
fi

if [ "$IS_MAC" = true ]; then
    # macOS detected, skip Linux detection
    :
elif [ -f /etc/debian_version ]; then
    IS_DEBIAN=true
    DETECTED_DISTRO="debian"
    echo -e "${GREEN}✓${NC} Debian-based Linux detected"
elif [ -f /etc/arch-release ] || [ -f /etc/artix-release ]; then
    IS_ARCH=true
    DETECTED_DISTRO="arch"
    echo -e "${GREEN}✓${NC} Arch Linux detected"
elif [[ "$OS_ID" == "debian" || "$OS_ID" == "ubuntu" || "$OS_ID" == "linuxmint" || "$OS_ID" == "pop" || "$OS_ID" == "pop-os" || "$OS_ID" == "pop_os" || "$OS_ID" == "elementary" || "$OS_LIKE" == *"debian"* || "$OS_LIKE" == *"ubuntu"* ]]; then
    IS_DEBIAN=true
    DETECTED_DISTRO="debian"
    echo -e "${GREEN}✓${NC} Debian-based Linux detected (via os-release)"
elif [[ "$OS_ID" == "arch" || "$OS_ID" == "archlinux" || "$OS_ID" == "manjaro" || "$OS_ID" == "endeavouros" || "$OS_ID" == "endeavour" || "$OS_ID" == "arcolinux" || "$OS_ID" == "garuda" || "$OS_ID" == "artix" || "$OS_ID" == "blackarch" || "$OS_LIKE" == *"arch"* ]]; then
    IS_ARCH=true
    DETECTED_DISTRO="arch"
    echo -e "${GREEN}✓${NC} Arch-based Linux detected (via os-release)"
elif command -v apt-get &>/dev/null; then
    IS_DEBIAN=true
    DETECTED_DISTRO="debian"
    echo -e "${GREEN}✓${NC} Debian-based Linux detected (via package manager)"
elif command -v pacman &>/dev/null; then
    IS_ARCH=true
    DETECTED_DISTRO="arch"
    echo -e "${GREEN}✓${NC} Arch-based Linux detected (via package manager)"
else
    echo -e "${YELLOW}⚠${NC}  Unsupported distribution detected"
    echo ""
    echo "ZDTT Terminal is optimized for Debian-based and Arch Linux systems."
    echo ""
    echo "Running on an unsupported system may result in:"
    echo "  • Some commands may not work as expected"
    echo "  • Auto-install features (like fastfetch) will not work"
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

echo "Detected distribution: ${DETECTED_DISTRO}"
read -p "Override detection? (debian/arch/mac/other, Enter to keep): " -r USER_OVERRIDE
USER_OVERRIDE=$(echo "$USER_OVERRIDE" | tr '[:upper:]' '[:lower:]')

case "$USER_OVERRIDE" in
    debian)
        IS_DEBIAN=true
        IS_ARCH=false
        IS_MAC=false
        DETECTED_DISTRO="debian"
        echo "Override applied: Debian-based system selected."
        ;;
    arch)
        IS_DEBIAN=false
        IS_ARCH=true
        IS_MAC=false
        DETECTED_DISTRO="arch"
        echo "Override applied: Arch-based system selected."
        ;;
    mac)
        IS_DEBIAN=false
        IS_ARCH=false
        IS_MAC=true
        DETECTED_DISTRO="mac"
        echo "Override applied: macOS selected."
        ;;
    other)
        IS_DEBIAN=false
        IS_ARCH=false
        IS_MAC=false
        DETECTED_DISTRO="other"
        echo "Override applied: Unsupported/Other selected."
        ;;
    "")
        echo "Keeping detected distribution."
        ;;
    *)
        echo "Unknown override '$USER_OVERRIDE'. Keeping detected distribution."
        ;;
esac

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed"
    echo ""
    
    if [ "$IS_MAC" = true ]; then
        echo "Checking for Homebrew..."
        BREW_PATH=""
        if command -v brew &> /dev/null; then
            BREW_PATH="brew"
        elif [ -f "/opt/homebrew/bin/brew" ]; then
            BREW_PATH="/opt/homebrew/bin/brew"
        elif [ -f "/usr/local/bin/brew" ]; then
            BREW_PATH="/usr/local/bin/brew"
        fi
        
        if [ -n "$BREW_PATH" ]; then
            echo "Installing Python 3 via Homebrew..."
            $BREW_PATH install python3
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to install Python 3${NC}"
                echo "Please install Python 3 manually: $BREW_PATH install python3"
                echo ""
                echo "Press any key to exit..."
                read -n 1 -s -r
                exit 1
            fi
            
            echo -e "${GREEN}✓${NC} Python 3 installed successfully"
        else
            echo -e "${RED}Homebrew is not installed.${NC}"
            echo ""
            echo "Homebrew is required for package management on macOS."
            echo ""
            read -p "Would you like to install Homebrew now? (yes/no): " -r
            echo ""
            if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                echo "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                
                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}✓${NC} Homebrew installed successfully"
                    echo ""
                    echo "Adding Homebrew to PATH..."
                    # Add Homebrew to PATH for this session
                    if [ -d "/opt/homebrew/bin" ]; then
                        export PATH="/opt/homebrew/bin:$PATH"
                        eval "$(/opt/homebrew/bin/brew shellenv)"
                    elif [ -d "/usr/local/bin" ]; then
                        export PATH="/usr/local/bin:$PATH"
                        eval "$(/usr/local/bin/brew shellenv)"
                    fi
                    echo ""
                    echo "Installing Python 3..."
                    brew install python3
                    
                    if [ $? -ne 0 ]; then
                        echo -e "${RED}Failed to install Python 3${NC}"
                        echo "Please install Python 3 manually: brew install python3"
                        echo ""
                        echo "Press any key to exit..."
                        read -n 1 -s -r
                        exit 1
                    fi
                    
                    echo -e "${GREEN}✓${NC} Python 3 installed successfully"
                else
                    echo -e "${RED}Failed to install Homebrew${NC}"
                    echo "Please install Homebrew manually:"
                    echo "  /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                    echo ""
                    echo "Press any key to exit..."
                    read -n 1 -s -r
                    exit 1
                fi
            else
                echo -e "${RED}Python 3 is required but cannot be installed without Homebrew.${NC}"
                echo ""
                echo "Please install Homebrew and Python 3 manually:"
                echo "  /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo "  brew install python3"
                echo ""
                echo "Press any key to exit..."
                read -n 1 -s -r
                exit 1
            fi
        fi
    elif [ "$IS_DEBIAN" = true ]; then
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
    elif [ "$IS_ARCH" = true ]; then
        echo "Installing Python 3..."
        
        # Sync package databases and install Python
        sudo pacman -Sy --noconfirm python
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install Python 3${NC}"
            echo "Please install Python 3 manually: sudo pacman -S python"
            echo ""
            echo "Press any key to exit..."
            read -n 1 -s -r
            exit 1
        fi
        
        echo -e "${GREEN}✓${NC} Python 3 installed successfully"
    else
        echo -e "${RED}Python 3 is required but auto-install is not supported on this distribution.${NC}"
        echo ""
        echo "Please install Python 3 manually using your package manager:"
        echo "  • Debian/Ubuntu: sudo apt-get install python3"
        echo "  • Arch/Manjaro: sudo pacman -S python"
        echo "  • macOS: brew install python3"
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
#!/usr/bin/env bash
#
# ZDTT Terminal Wrapper
# Compatible with both bash and zsh
#

ZDTT_DIR="$HOME/.local/share/zdtt"

case "$1" in
    start)
        # Clear screen before starting ZDTT
        clear
        python3 "$ZDTT_DIR/terminal.py"
        ;;
    update)
        # Check for auto-update flag
        AUTO_UPDATE=false
        if [[ "$2" == "--auto" ]] || [[ "$2" == "--yes" ]]; then
            AUTO_UPDATE=true
        fi
        
        echo "Checking for updates..."
        echo ""
        
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
            echo "🔔 Update available!"
            echo ""
            
            # Auto-update if flag is set, otherwise prompt
            if [ "$AUTO_UPDATE" = true ]; then
                REPLY="yes"
                echo "Auto-updating..."
                echo ""
            else
                read -p "Do you want to update now? (yes/no): " -r
                echo ""
            fi
            
            if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
                echo "Updating ZDTT Terminal..."
                echo ""
                
                # Download updated files
                BASE_URL="https://zdtt-sources.zane.org"
                UPDATE_FAILED=false
                
                # Update terminal.py
                echo "Downloading terminal.py..."
                if command -v wget &> /dev/null; then
                    wget -q "$BASE_URL/terminal.py" -O "$ZDTT_DIR/terminal.py" 2>/dev/null || UPDATE_FAILED=true
                elif command -v curl &> /dev/null; then
                    curl -sSL "$BASE_URL/terminal.py" -o "$ZDTT_DIR/terminal.py" 2>/dev/null || UPDATE_FAILED=true
                fi
                
                if [ "$UPDATE_FAILED" = true ]; then
                    echo "✗ Failed to download terminal.py"
                    exit 1
                fi
                echo "✓ terminal.py updated"
                
                # Update version.txt
                echo "Downloading version.txt..."
                if command -v wget &> /dev/null; then
                    wget -q "$BASE_URL/version.txt" -O "$ZDTT_DIR/version.txt" 2>/dev/null || UPDATE_FAILED=true
                elif command -v curl &> /dev/null; then
                    curl -sSL "$BASE_URL/version.txt" -o "$ZDTT_DIR/version.txt" 2>/dev/null || UPDATE_FAILED=true
                fi
                
                if [ "$UPDATE_FAILED" = true ]; then
                    echo "✗ Failed to download version.txt"
                    exit 1
                fi
                echo "✓ version.txt updated"
                
                # Set permissions
                chmod +x "$ZDTT_DIR/terminal.py"
                
                echo ""
                echo "==========================================="
                echo "✓ Update complete!"
                echo "==========================================="
                echo ""
                echo "ZDTT Terminal has been updated to v$REMOTE_VERSION"
                echo ""
                echo "Your settings are preserved:"
                echo "  • Command history: ~/.zdtt_history"
                echo "  • Aliases: ~/.zdtt/aliases"
                echo "  • Plugins: ~/.zdtt/plugins/"
                echo "  • Custom banner: ~/.zdtt/banner.txt"
                echo ""
                echo "Run 'zdtt start' to use the updated version."
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
    github)
        GITHUB_URL="https://github.com/ZaneThePython/ZDTT"
        echo "Opening ZDTT GitHub repository..."
        
        # Detect platform and use appropriate command to open URL
        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS
            open "$GITHUB_URL"
        elif command -v xdg-open &> /dev/null; then
            # Linux (most distributions)
            xdg-open "$GITHUB_URL"
        elif command -v x-www-browser &> /dev/null; then
            # Linux (Debian/Ubuntu fallback)
            x-www-browser "$GITHUB_URL"
        elif command -v gnome-open &> /dev/null; then
            # Linux (GNOME fallback)
            gnome-open "$GITHUB_URL"
        else
            # Fallback: print URL and let user open manually
            echo "Please open this URL in your browser:"
            echo "$GITHUB_URL"
        fi
        ;;
    *)
        echo "ZDTT Terminal"
        echo ""
        echo "Usage:"
        echo "  zdtt start        - Start the ZDTT Terminal"
        echo "  zdtt update       - Check for and install updates"
        echo "  zdtt installer    - Run installer (for updates/reinstall)"
        echo "  zdtt version      - Display version information"
        echo "  zdtt github       - Open ZDTT GitHub repository"
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
    
    # Detect user's default shell (not the script's shell)
    # Priority: 1) Check if running in zsh, 2) Check if .zshrc exists, 3) Check $SHELL, 4) Check /etc/passwd, 5) Default to bash
    SHELL_CONFIG="$HOME/.bashrc"
    SHELL_NAME="bash"
    
    # Check if running in zsh (most reliable - immediate detection)
    if [[ -n "$ZSH_VERSION" ]]; then
        SHELL_CONFIG="$HOME/.zshrc"
        SHELL_NAME="zsh"
    # Check if .zshrc exists (strong indicator user uses zsh)
    elif [ -f "$HOME/.zshrc" ]; then
        SHELL_CONFIG="$HOME/.zshrc"
        SHELL_NAME="zsh"
    # Check $SHELL environment variable
    elif [[ -n "$SHELL" ]] && [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_CONFIG="$HOME/.zshrc"
        SHELL_NAME="zsh"
    # Check user's default shell from /etc/passwd
    else
        USER_SHELL=""
        if command -v getent &> /dev/null; then
            USER_SHELL=$(getent passwd "$USER" 2>/dev/null | cut -d: -f7)
        elif [ -f /etc/passwd ]; then
            USER_SHELL=$(grep "^$USER:" /etc/passwd 2>/dev/null | cut -d: -f7)
        fi
        
        if [[ -n "$USER_SHELL" ]] && [[ "$USER_SHELL" == *"zsh"* ]]; then
            SHELL_CONFIG="$HOME/.zshrc"
            SHELL_NAME="zsh"
        fi
    fi
    
    echo -e "${GREEN}Detected shell: ${SHELL_NAME}${NC}"
    echo -e "Config file: ${SHELL_CONFIG}"
    echo ""
    echo "To use the 'zdtt' command, add the following line to your $SHELL_CONFIG:"
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run: source $SHELL_CONFIG"
    echo ""
    
    # Ask if user wants to add it automatically
    read -p "Would you like to add it to your $SHELL_CONFIG now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Create the config file if it doesn't exist
        if [ ! -f "$SHELL_CONFIG" ]; then
            touch "$SHELL_CONFIG"
        fi
        
        # Check if the PATH line already exists (check for various formats)
        PATH_ALREADY_SET=false
        if grep -q '\.local/bin' "$SHELL_CONFIG" 2>/dev/null; then
            PATH_ALREADY_SET=true
        fi
        
        if [ "$PATH_ALREADY_SET" = false ]; then
            echo "" >> "$SHELL_CONFIG"
            echo "# Added by ZDTT Terminal installer" >> "$SHELL_CONFIG"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_CONFIG"
            echo -e "${GREEN}✓${NC} Added to $SHELL_CONFIG"
            echo ""
            echo "To apply the changes, run:"
            echo "  source $SHELL_CONFIG"
            echo ""
            echo "Or open a new terminal window."
        else
            echo -e "${GREEN}✓${NC} PATH already configured in $SHELL_CONFIG"
            echo ""
            echo "If 'zdtt' command is not available, run:"
            echo "  source $SHELL_CONFIG"
            echo ""
        fi
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

