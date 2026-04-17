@echo off
echo =^> Bootstraping Polymarket Agent Environment...

if not exist .env (
    echo =^> 1. Creating .env from .env.example
    copy .env.example .env
) else (
    echo =^> 1. .env already exists. Skipping.
)

echo =^> 2. Creating python virtual environment
python -m venv venv
call venv\Scripts\activate.bat

echo =^> 3. Installing dependencies
pip install -e .[dev]

echo =^> 4. (Optional) Run Database Migration
echo If Docker Postgres is up, run: make db-upgrade

echo =^> 5. Environment Ready! Run 'make dev' to start.
