#!/bin/bash
set -e

cd backend
gunicorn decisiobi.wsgi:application --bind 127.0.0.1:8000 --daemon --pid /tmp/gunicorn.pid
cd ..

cd decision-spark
exec node server-node.mjs
