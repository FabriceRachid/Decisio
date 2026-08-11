#!/bin/bash
set -e

echo "=== Building frontend ==="
cd decision-spark
npm install
npm run build
cd ..

echo "=== Generating index.html ==="
ENTRY_JS=$(basename $(ls decision-spark/dist/client/assets/index-*.js | head -1))
echo "Entry JS: $ENTRY_JS"

cat > decision-spark/dist/client/index.html <<HTMLEOF
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>DécisioBI</title>
<link rel="icon" type="image/png" href="/favicon.png" />
</head>
<body>
<div id="root"></div>
<script type="module" src="/assets/${ENTRY_JS}"></script>
</body>
</html>
HTMLEOF

echo "=== Copying to backend/frontend ==="
mkdir -p backend/frontend
rm -rf backend/frontend/assets
cp -r decision-spark/dist/client/* backend/frontend/

echo "=== Frontend build complete ==="
ls -la backend/frontend/
ls -la backend/frontend/assets/ | head -5
