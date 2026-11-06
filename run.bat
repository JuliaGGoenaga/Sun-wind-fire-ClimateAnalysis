@echo off
REM Crea el entorno la primera vez y arranca la webapp en http://localhost:8000
cd /d "%~dp0"
.venv\Scripts\python -c "import uvicorn, ladybug" >nul 2>&1
if errorlevel 1 (
  if exist .venv rmdir /s /q .venv
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\pip install -q -r requirements.txt
)
start "" http://localhost:8000
.venv\Scripts\uvicorn app.main:app --port 8000
