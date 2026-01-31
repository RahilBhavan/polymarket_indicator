#!/bin/bash
#
# Development runner for CryptoSignal bot
# Starts the FastAPI server with auto-reload for development
#

set -e

# Get project root
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  CryptoSignal Bot - Development Mode${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    echo ""
    echo "Run setup first:"
    echo "  ./scripts/setup.sh"
    echo ""
    exit 1
fi

# Validate environment
echo "Validating environment..."
if uv run python scripts/validate_env.py --quiet; then
    echo -e "${GREEN}✅ Configuration valid${NC}"
else
    echo "❌ Configuration validation failed"
    echo "Fix errors in .env and try again"
    exit 1
fi

echo ""
echo "Starting development server with auto-reload..."
echo "Server will be available at: http://localhost:8000"
echo "Health check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start uvicorn with reload
uv run uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir src/app
