#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit

pip install -r requirements.txt

# Install Playwright Chromium (optional — app works without it via httpx)
pip install playwright
playwright install chromium || echo "Playwright chromium install failed — will use httpx only"
