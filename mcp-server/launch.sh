#!/bin/bash

# OpenGraph AI MCP Server Launch Script
# This script starts the MCP server and handles environment setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}OpenGraph AI MCP Server${NC}"
echo "=========================="

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js not installed${NC}"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✓${NC} Node.js $NODE_VERSION"

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm not installed${NC}"
    exit 1
fi

NPM_VERSION=$(npm --version)
echo -e "${GREEN}✓${NC} npm $NPM_VERSION"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} $PYTHON_VERSION"

# Check if node_modules exists
if [ ! -d "$SCRIPT_DIR/node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    cd "$SCRIPT_DIR"
    npm install
fi

# Check if TypeScript is built
if [ ! -d "$SCRIPT_DIR/dist" ]; then
    echo -e "${YELLOW}Building TypeScript...${NC}"
    cd "$SCRIPT_DIR"
    npm run build
fi

# Check environment variables
echo ""
echo "Environment Configuration:"

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠${NC} OPENAI_API_KEY not set"
else
    echo -e "${GREEN}✓${NC} OPENAI_API_KEY configured"
fi

if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${YELLOW}⚠${NC} GCP_PROJECT_ID not set"
else
    echo -e "${GREEN}✓${NC} GCP_PROJECT_ID: $GCP_PROJECT_ID"
fi

if [ -z "$NEO4J_URI" ]; then
    echo -e "${YELLOW}⚠${NC} NEO4J_URI not set"
else
    echo -e "${GREEN}✓${NC} NEO4J_URI configured"
fi

if [ -z "$GCS_BUCKET" ]; then
    echo -e "${YELLOW}⚠${NC} GCS_BUCKET not set"
else
    echo -e "${GREEN}✓${NC} GCS_BUCKET: $GCS_BUCKET"
fi

# Set Python executable if not set
if [ -z "$PYTHON_EXECUTABLE" ]; then
    export PYTHON_EXECUTABLE=$(which python3)
    echo -e "${GREEN}✓${NC} PYTHON_EXECUTABLE: $PYTHON_EXECUTABLE"
else
    echo -e "${GREEN}✓${NC} PYTHON_EXECUTABLE: $PYTHON_EXECUTABLE"
fi

# Start the MCP server
echo ""
echo -e "${GREEN}Starting MCP server...${NC}"
echo "=========================="

cd "$SCRIPT_DIR"
npm run start
