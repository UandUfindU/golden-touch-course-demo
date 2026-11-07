#!/bin/bash
echo "==================================================="
echo "      Golden Touch Quant OS - Backend Startup"
echo "==================================================="

# Start Backend
echo "[1/1] Starting Backend Server (Port 8000)..."
cd backend
nohup uvicorn app.main:app --reload --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > ../backend.pid

echo ""
echo "Backend is starting..."
echo "---------------------------------------"
echo "[Backend API] http://localhost:8000/docs"
echo "[Backend PID] $BACKEND_PID"
echo "[Backend Log] logs/backend.log"
echo "---------------------------------------"
echo "Use ./stop_app.sh to stop the service."
