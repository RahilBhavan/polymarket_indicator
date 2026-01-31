#!/bin/bash
#
# CryptoSignal Bot - One-Command Setup Script
# ===========================================
#
# This script handles complete initialization:
# - Checks prerequisites (Python 3.11+, PostgreSQL)
# - Installs uv package manager if needed
# - Creates .env from template with interactive prompts
# - Validates environment configuration
# - Installs dependencies
# - Initializes database with migrations
# - Displays next steps
#
# Usage:
#   ./scripts/setup.sh [--non-interactive] [--skip-db]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
NON_INTERACTIVE=false
SKIP_DB=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --skip-db)
            SKIP_DB=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --non-interactive  Run without prompts (requires existing .env)"
            echo "  --skip-db          Skip database initialization"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac
done

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Get project root (parent of scripts/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

print_header "CryptoSignal Bot - Setup"

echo "This script will set up the CryptoSignal bot from scratch."
echo "It will:"
echo "  1. Check prerequisites"
echo "  2. Install uv package manager (if needed)"
echo "  3. Create .env configuration file"
echo "  4. Install Python dependencies"
echo "  5. Initialize the database"
echo ""

if [ "$NON_INTERACTIVE" = false ]; then
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
fi

# Step 1: Check Python version
print_header "1. Checking Prerequisites"

if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    echo "Please install Python 3.11 or later:"
    echo "  - macOS: brew install python@3.11"
    echo "  - Ubuntu/Debian: sudo apt install python3.11"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
    print_error "Python 3.11+ required (found $PYTHON_VERSION)"
    echo "Please upgrade Python:"
    echo "  - macOS: brew install python@3.11"
    echo "  - Ubuntu/Debian: sudo apt install python3.11"
    exit 1
fi

print_success "Python $PYTHON_VERSION detected"

# Check if PostgreSQL is accessible
if ! command -v psql &> /dev/null; then
    print_warning "psql command not found"
    print_info "PostgreSQL client tools recommended but not required"
    print_info "See docs/SETUP_GUIDE.md for PostgreSQL installation"
else
    print_success "PostgreSQL client tools available"
fi

# Step 2: Install uv if needed
print_header "2. Package Manager"

if command -v uv &> /dev/null; then
    print_success "uv package manager already installed"
else
    print_info "Installing uv package manager..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        print_success "uv installed successfully"
        # Add uv to PATH for this session
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        print_error "Failed to install uv"
        echo "Please install manually: https://github.com/astral-sh/uv"
        exit 1
    fi
fi

# Step 3: Create .env file
print_header "3. Configuration"

if [ -f .env ]; then
    print_warning ".env file already exists"
    if [ "$NON_INTERACTIVE" = false ]; then
        read -p "Overwrite? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Using existing .env file"
        else
            rm .env
            cp .env.example .env
            print_success "Created fresh .env from template"
        fi
    fi
else
    cp .env.example .env
    print_success "Created .env from template"
fi

# Interactive configuration
if [ "$NON_INTERACTIVE" = false ] && [ ! -s .env ]; then
    echo ""
    echo "Let's configure your bot. You'll need:"
    echo "  - Telegram bot token (from @BotFather)"
    echo "  - PostgreSQL database URL"
    echo ""

    # Telegram Bot Token
    read -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        sed -i.bak "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN|" .env
    fi

    # Webhook Secret (generate if not provided)
    read -p "Telegram Webhook Secret (leave empty to generate): " TELEGRAM_WEBHOOK_SECRET
    if [ -z "$TELEGRAM_WEBHOOK_SECRET" ]; then
        TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)
        print_info "Generated webhook secret: $TELEGRAM_WEBHOOK_SECRET"
    fi
    sed -i.bak "s|TELEGRAM_WEBHOOK_SECRET=.*|TELEGRAM_WEBHOOK_SECRET=$TELEGRAM_WEBHOOK_SECRET|" .env

    # Allowed User IDs
    read -p "Telegram User ID(s) (comma-separated): " TELEGRAM_ALLOWED_USER_IDS
    if [ -n "$TELEGRAM_ALLOWED_USER_IDS" ]; then
        sed -i.bak "s|TELEGRAM_ALLOWED_USER_IDS=.*|TELEGRAM_ALLOWED_USER_IDS=$TELEGRAM_ALLOWED_USER_IDS|" .env
    fi

    # Database URL
    echo ""
    print_info "PostgreSQL database configuration"
    read -p "Database URL (default: postgresql://cryptosignal:changeme@localhost:5432/cryptosignal): " DATABASE_URL
    if [ -z "$DATABASE_URL" ]; then
        DATABASE_URL="postgresql://cryptosignal:changeme@localhost:5432/cryptosignal"
    fi
    sed -i.bak "s|DATABASE_URL=.*|DATABASE_URL=$DATABASE_URL|" .env

    # Clean up backup files
    rm -f .env.bak

    print_success "Configuration saved to .env"
fi

# Validate environment
print_info "Validating configuration..."
if uv run python scripts/validate_env.py --quiet; then
    print_success "Configuration valid"
else
    print_error "Configuration validation failed"
    echo ""
    echo "Please edit .env and set the required values:"
    echo "  - TELEGRAM_BOT_TOKEN"
    echo "  - TELEGRAM_WEBHOOK_SECRET"
    echo "  - TELEGRAM_ALLOWED_USER_IDS"
    echo "  - DATABASE_URL"
    echo ""
    echo "See docs/SETUP_GUIDE.md for detailed instructions"
    exit 1
fi

# Step 4: Install dependencies
print_header "4. Installing Dependencies"

print_info "Installing Python packages with uv..."
if uv sync --all-extras; then
    print_success "Dependencies installed"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Step 5: Initialize database
if [ "$SKIP_DB" = false ]; then
    print_header "5. Database Initialization"

    print_info "Initializing database schema and migrations..."
    if uv run python scripts/init_db.py; then
        print_success "Database initialized"
    else
        print_error "Database initialization failed"
        echo ""
        echo "Common issues:"
        echo "  - PostgreSQL server not running"
        echo "  - Database credentials incorrect in DATABASE_URL"
        echo "  - Database does not exist (create it first)"
        echo ""
        echo "See docs/TROUBLESHOOTING.md for help"
        exit 1
    fi
else
    print_warning "Skipping database initialization (--skip-db flag)"
fi

# Success!
print_header "Setup Complete! 🎉"

echo "Your CryptoSignal bot is ready to run!"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start the bot:"
echo "     ${GREEN}./scripts/dev.sh${NC}"
echo ""
echo "  2. Set up Telegram webhook (after deploying with HTTPS):"
echo "     curl -X POST \"https://api.telegram.org/bot<TOKEN>/setWebhook\" \\"
echo "       -d \"url=https://your-domain.com/webhook/telegram\" \\"
echo "       -d \"secret_token=<WEBHOOK_SECRET>\""
echo ""
echo "  3. Test the bot:"
echo "     - Send /start to your bot on Telegram"
echo "     - Send /signal to get a daily signal"
echo ""
echo "For local testing with webhook, use ngrok:"
echo "  ${BLUE}ngrok http 8000${NC}"
echo ""
echo "Documentation:"
echo "  - Quick Start:     docs/QUICK_START.md"
echo "  - Setup Guide:     docs/SETUP_GUIDE.md"
echo "  - Troubleshooting: docs/TROUBLESHOOTING.md"
echo ""

# Reminder about webhook setup
print_warning "Don't forget to set up your Telegram webhook!"
echo "  Without webhook setup, the bot won't receive messages."
echo "  For local development, use ngrok for HTTPS tunnel."
echo ""
