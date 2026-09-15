@echo off
REM Least-privilege durable Atlas governor host for Windows.
REM Primary continuation backend: Cursor SDK. MERGE_AUTHORIZATION=NOT_GRANTED.
setlocal
set ROOT=%~dp0..
set PYTHONPATH=%ROOT%\src;%PYTHONPATH%
python -m project_atlas.cli orchestrator governor-service-run --root "%ROOT%" %*
endlocal
