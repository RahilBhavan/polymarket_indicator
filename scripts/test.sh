#!/bin/bash
#
# Test runner for CryptoSignal bot
# Runs pytest with coverage reporting
#

set -e

# Get project root
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parse arguments
COVERAGE=false
VERBOSE=false
PATTERN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        -k)
            PATTERN="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -c, --coverage   Run with coverage reporting"
            echo "  -v, --verbose    Verbose output"
            echo "  -k PATTERN       Run tests matching pattern"
            echo "  -h, --help       Show this help"
            echo ""
            echo "Examples:"
            echo "  ./scripts/test.sh                    # Run all tests"
            echo "  ./scripts/test.sh --coverage         # Run with coverage"
            echo "  ./scripts/test.sh -k test_health     # Run specific test"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  CryptoSignal Bot - Test Suite${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Build pytest command
PYTEST_CMD="uv run pytest"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ -n "$PATTERN" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $PATTERN"
fi

if [ "$COVERAGE" = true ]; then
    echo "Running tests with coverage..."
    PYTEST_CMD="$PYTEST_CMD --cov=src/app --cov-report=term-missing --cov-report=html"
else
    echo "Running tests..."
fi

echo ""

# Run tests
if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  ✅ Tests Passed${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if [ "$COVERAGE" = true ]; then
        echo "Coverage report saved to: htmlcov/index.html"
        echo "Open with: open htmlcov/index.html"
        echo ""
    fi

    exit 0
else
    echo ""
    echo "❌ Tests failed"
    exit 1
fi
