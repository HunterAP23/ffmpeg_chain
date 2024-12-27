#!/bin/bash

# Array of Python versions to test
versions=(
    "3.9"
    "3.10"
    "3.11"
    "3.12"
    "3.13" # psutil currently does not support 3.13t
)

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed${NC}"
    echo "Please install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Function to run tests with specific configuration
run_test_configuration() {
    local version=$1
    local with_psutil=$2
    shift 2  # Remove version and with_psutil from arguments
    
    local venv_name="pytest-py${version/./}-${with_psutil:+with}-${with_psutil:-without}-psutil"
    echo -e "${YELLOW}Running tests with Python ${version} (${with_psutil:+with}-${with_psutil:-without} psutil) in venv ${venv_name}${NC}"
    echo "----------------------------------------"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv/${venv_name}" ]; then
        echo "Creating virtual environment for Python ${version}..."
        uv venv ".venv/${venv_name}" --python="${version}" || {
            echo -e "${RED}Failed to create virtual environment for Python ${version}${NC}"
            return 1
        }
    fi

    # Activate virtual environment
    echo "Activating virtual environment..."
    source ".venv/${venv_name}/bin/activate" || {
        echo -e "${RED}Failed to activate virtual environment for Python ${version}${NC}"
        return 1
    }

    # Install or uninstall psutil based on configuration
    if [ -n "$with_psutil" ]; then
        echo "Installing psutil..."
        uv pip install psutil || {
            echo -e "${RED}Failed to install psutil${NC}"
            deactivate
            return 1
        }
    else
        # Ensure psutil is not installed
        if python -c "import psutil" 2>/dev/null; then
            echo "Removing psutil..."
            uv pip uninstall -y psutil || {
                echo -e "${RED}Failed to remove psutil${NC}"
                deactivate
                return 1
            }
        fi
    fi

    # Install pytest if not already installed
    if ! python -c "import pytest" 2>/dev/null; then
        echo "Installing pytest..."
        uv pip install pytest || {
            echo -e "${RED}Failed to install pytest for Python ${version}${NC}"
            deactivate
            return 1
        }
    fi
    
    # Run tests using pytest directly in the activated environment
    echo -e "${BLUE}Running tests...${NC}"
    if pytest "$@"; then
        echo -e "${GREEN}✓ Tests passed for Python ${version} (${with_psutil:+with}-${with_psutil:-without} psutil)${NC}"
        local exit_code=0
    else
        local exit_code=$?
        echo -e "${RED}✗ Tests failed for Python ${version} (${with_psutil:+with}-${with_psutil:-without} psutil)${NC}"
    fi

    # Deactivate virtual environment
    echo "Deactivating virtual environment..."
    deactivate

    return $exit_code
}

# Track overall success
overall_success=true

# Create .venv directory if it doesn't exist
mkdir -p .venv

# Run tests for each version, both with and without psutil
for version in "${versions[@]}"; do
    # Run tests without psutil
    if ! run_test_configuration "$version" "" "$@"; then
        overall_success=false
    fi
    echo

    # Run tests with psutil
    if ! run_test_configuration "$version" "yes" "$@"; then
        overall_success=false
    fi
    echo
done

# Final summary
if [ "$overall_success" = true ]; then
    echo -e "${GREEN}All test runs completed successfully${NC}"
    exit 0
else
    echo -e "${RED}Some test runs failed${NC}"
    exit 1
fi