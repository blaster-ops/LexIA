@echo off 
title Servidor LexIA - Ejecutandose 
chcp 65001 > NUL 
echo ============================================================ 
echo             LEXIA - SERVIDOR INICIADO 
echo ============================================================ 
.\venv\Scripts\uvicorn main:app --reload --host 0.0.0.0 --port 8000 
