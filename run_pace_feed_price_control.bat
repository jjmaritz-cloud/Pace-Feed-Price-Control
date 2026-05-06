@echo off
start "Pace Feed Price Control" cmd /k "cd /d "C:\Pace Feed Price Control" && py -3.12 -m streamlit run app.py"
exit