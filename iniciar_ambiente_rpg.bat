@echo off
title RPG de Mesa - Ambiente IA (ai-memory + Sync Daemon)
cd /d "%~dp0"

echo ============================================================
echo   AMBIENTE DE RPG DE MESA - NARRATIVE ENGINE + AI-MEMORY
echo ============================================================
echo.
echo Iniciando sincronizador e servidor de memoria persistente...
echo.

python sync_daemon.py
pause
