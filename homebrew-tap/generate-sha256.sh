#!/bin/bash
# Script to generate SHA256 for Homebrew formula after release

TAG=$1

if [ -z "$TAG" ]; then
    echo "Usage: $0 <tag>"
    echo "Example: $0 v0.1.0"
    exit 1
fi

URL="https://github.com/anomalyco/ask/archive/refs/tags/${TAG}.tar.gz"
echo "Fetching ${URL}..."

SHA256=$(curl -sL "$URL" | shasum -a 256 | awk '{print $1}')

echo ""
echo "Add this to homebrew-tap/ask.rb:"
echo ""
echo "  url \"https://github.com/anomalyco/ask/archive/refs/tags/${TAG}.tar.gz\""
echo "  sha256 \"${SHA256}\""
