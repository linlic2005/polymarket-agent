#!/usr/bin/env bash
set -e

echo "=> Bootstraping Polymarket Agent Environment..."

if [ ! -f .env ]; then
    echo "=> 1. Creating .env from .env.example"
    cp .env.example .env
else
    echo "=> 1. .env already exists. Skipping."
fi

echo "=> 2. Creating python virtual environment"
python3 -m venv venv
source venv/bin/activate

echo "=> 3. Installing dependencies"
pip install -e .[dev]

echo "=> 4. (Optional) Run Database Migration"
echo "If Docker Postgres is up, run: make db-upgrade"

echo "=> 5. Environment Ready! Run 'make dev' to start."
