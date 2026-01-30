#!/bin/bash
# Quick start script for the lead capture system

echo "🚀 Starting AI-Powered Lead Capture System..."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env with your API keys before running again."
    echo ""
    echo "Required:"
    echo "  - OPENAI_API_KEY"
    echo "  - SUPABASE_URL"
    echo "  - SUPABASE_KEY"
    exit 1
fi

# Run setup check
echo "🔍 Checking setup..."
python3 check_setup.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Starting server..."
    echo "📍 Access the system at: http://localhost:5000"
    echo "📍 Dashboard at: http://localhost:5000/dashboard"
    echo ""
    python3 app.py
else
    echo ""
    echo "❌ Setup incomplete. Please fix the issues above."
    exit 1
fi
