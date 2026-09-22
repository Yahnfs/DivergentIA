@echo off
rem Atalho: de dois cliques para iniciar o DivergentIA (Ollama + servidor + navegador).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar.ps1"
if errorlevel 1 pause
