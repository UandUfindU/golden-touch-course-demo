#!/bin/bash
echo "==================================================="
echo "      Stopping Golden Touch Quant OS"
echo "==================================================="

echo "[1/1] Stopping Backend..."

# Try to kill using saved PID
if [ -f backend.pid ]; then
    PID=$(cat backend.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "   - Backend process ($PID) terminated."
        rm backend.pid
    else
        echo "   - PID $PID not running."
        rm backend.pid
    fi
fi

# Also try killing uvicorn processes
pkill -f "uvicorn app.main:app" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   - Uvicorn processes terminated."
fi

echo ""
echo "Backend service stopped."
