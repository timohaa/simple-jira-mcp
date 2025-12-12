#!/bin/bash
# Utility script to run linting, type checking, and tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="./venv/bin"
RUN_LINT=false
RUN_MYPY=false
RUN_TESTS=false
COVERAGE=false
FIX=false
PYTEST_ARGS=""

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -l, --lint       Run ruff linting"
    echo "  -m, --mypy       Run mypy type checking"
    echo "  -t, --tests      Run pytest tests"
    echo "  -c, --coverage   Run tests with coverage report (implies -t)"
    echo "  -f, --fix        Auto-fix linting issues (implies -l)"
    echo "  -a, --all        Run lint, mypy, and tests (default if no options)"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Additional arguments after -- are passed to pytest"
    echo ""
    echo "Examples:"
    echo "  $0               # Run all checks"
    echo "  $0 -l            # Run linting only"
    echo "  $0 -m            # Run mypy only"
    echo "  $0 -t            # Run tests only"
    echo "  $0 -c            # Run tests with coverage"
    echo "  $0 -f            # Auto-fix linting issues"
    echo "  $0 -t -- -v      # Run tests with verbose output"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -l|--lint)
            RUN_LINT=true
            shift
            ;;
        -m|--mypy)
            RUN_MYPY=true
            shift
            ;;
        -t|--tests)
            RUN_TESTS=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            RUN_TESTS=true
            shift
            ;;
        -f|--fix)
            FIX=true
            RUN_LINT=true
            shift
            ;;
        -a|--all)
            RUN_LINT=true
            RUN_MYPY=true
            RUN_TESTS=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        --)
            shift
            PYTEST_ARGS="$*"
            break
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Default: run all if no options specified
if [[ "$RUN_LINT" == "false" && "$RUN_MYPY" == "false" && "$RUN_TESTS" == "false" ]]; then
    RUN_LINT=true
    RUN_MYPY=true
    RUN_TESTS=true
fi

# Run ruff linting
if [[ "$RUN_LINT" == "true" ]]; then
    if [[ "$FIX" == "true" ]]; then
        echo "Running ruff with auto-fix..."
        $VENV/ruff check --fix src/ tests/
        $VENV/ruff format src/ tests/
    else
        echo "Running ruff linting..."
        $VENV/ruff check src/ tests/
        $VENV/ruff format --check src/ tests/
    fi
    echo ""
fi

# Run mypy
if [[ "$RUN_MYPY" == "true" ]]; then
    echo "Running mypy type checking..."
    $VENV/mypy src/
    echo ""
fi

# Run tests
if [[ "$RUN_TESTS" == "true" ]]; then
    if [[ "$COVERAGE" == "true" ]]; then
        echo "Running pytest with coverage..."
        $VENV/pytest --cov=src --cov-report=term-missing --cov-report=html $PYTEST_ARGS
        echo ""
        echo "HTML coverage report: htmlcov/index.html"
    else
        echo "Running pytest..."
        $VENV/pytest -q $PYTEST_ARGS
    fi
fi

echo "Done."
