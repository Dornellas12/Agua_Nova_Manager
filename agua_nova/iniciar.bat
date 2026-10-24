@echo off
cd /d "%~dp0"
echo Iniciando o sistema Agua Nova...
python -m streamlit run app.py
pause
