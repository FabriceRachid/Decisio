#!/bin/bash
set -e

echo "=== Building frontend ==="
cd decision-spark
npm install
npm run build

echo "=== Frontend build complete ==="
ls -la dist/server/
ls -la dist/client/
ls -la dist/client/assets/ | head -5
