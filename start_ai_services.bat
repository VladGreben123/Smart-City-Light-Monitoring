@echo off
echo Starting IT-Tupolev_2026 AI Services...

echo Starting Lamp Failure Prediction AI (Port 8001)...
start "AI Service (Port 8001)" cmd /k "cd AI && python main.py"

echo Starting Smart Drone Routing AI (Port 8002)...
start "Routing Service (Port 8002)" cmd /k "cd Routing-AI && python main.py"

echo Services started in separate windows.
echo If they close immediately, check if you have installed requirements:
echo pip install -r AI\requirements.txt
echo pip install -r Routing-AI\requirements.txt
pause
