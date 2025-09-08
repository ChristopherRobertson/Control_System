
#!/bin/bash

echo "🚀 Starting IR Spectroscopy Control Interface..."

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Start Backend
echo "🔧 Starting FastAPI Backend..."
cd backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Start Frontend
echo "🎨 Starting React Frontend..."
cd frontend
npm run dev -- --host 0.0.0.0 --port 5000 &
FRONTEND_PID=$!
cd ..

echo "✅ Services started successfully!"
echo "📱 Frontend: http://0.0.0.0:5000"
echo "🔌 Backend API: http://0.0.0.0:8000"
echo "📚 API Docs: http://0.0.0.0:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
