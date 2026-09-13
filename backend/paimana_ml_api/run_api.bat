@echo off
cd /d %~dp0
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
