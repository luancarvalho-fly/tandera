@echo off
rem O Tandera: um motor de analise so, sempre o mais novo. Uso: tandera analisar <video> [--pecas ...] · tandera versao
set PYTHONIOENCODING=utf-8
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%~dp0.venv\Scripts\python.exe" -m tandera %*
