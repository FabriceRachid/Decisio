#!/bin/bash
set -e

echo "=== Building frontend ==="
cd decision-spark
npm install
npm run build

echo "=== Preparing SPA dist ==="
rm -rf ../backend/frontend
mkdir -p ../backend/frontend/assets

# Copy all client assets
cp -r dist/client/assets/* ../backend/frontend/assets/
cp dist/client/favicon.png ../backend/frontend/ 2>/dev/null || true
cp dist/client/logo.png ../backend/frontend/ 2>/dev/null || true

# Find the main JS entry (the largest index-*.js is the hydration bundle)
ENTRY_JS=$(ls -S dist/client/assets/index-*.js 2>/dev/null | head -1 | xargs basename 2>/dev/null)
CSS_FILE=$(ls dist/client/assets/index-*.css 2>/dev/null | head -1 | xargs basename 2>/dev/null)

echo "Entry JS: $ENTRY_JS"
echo "CSS: $CSS_FILE"

# Generate index.html for SPA client-side rendering
cat > ../backend/frontend/index.html << HTMLEOF
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#1e293b"/>
<link rel="icon" type="image/png" href="/static/favicon.png"/>
<link rel="stylesheet" href="/static/assets/$CSS_FILE"/>
</head>
<body>
<div id="root"></div>
<script type="module" src="/static/assets/$ENTRY_JS"></script>
</body>
</html>
HTMLEOF

echo "=== Frontend ready ==="
ls -la ../backend/frontend/
