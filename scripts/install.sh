#!/bin/bash
set -e

# Remove and recreate Python virtual environment
if [ -d ".venv" ]; then
  echo "Removing existing .venv..."
  rm -rf .venv
fi
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and install Python requirements
pip install --upgrade pip
pip install -r requirements.txt

deactivate

# Remove and recreate frontend node_modules
cd frontend
if [ -d "node_modules" ]; then
  echo "Removing existing node_modules..."
  rm -rf node_modules
fi
npm install
cd ..

echo "\nSetup complete!" 