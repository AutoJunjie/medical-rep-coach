#!/usr/bin/env python3
"""
Complete startup script for Med Coach with streaming transcription
Starts both backend (Flask + WebSocket) and frontend (static file server)
"""
import os
import sys
import subprocess
import time
import threading
import webbrowser
from dotenv import load_dotenv

def start_backend():
    """Start the backend Flask application with WebSocket server"""
    print("🚀 Starting backend server (Flask + WebSocket)...")
    try:
        subprocess.run([sys.executable, 'main.py'], check=True)
    except KeyboardInterrupt:
        print("\n👋 Backend server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Backend server failed: {e}")

def start_frontend():
    """Start the frontend static file server"""
    print("🌐 Starting frontend server...")
    try:
        # Wait a bit for backend to start
        time.sleep(2)
        subprocess.run([sys.executable, '-m', 'http.server', '5001'], check=True)
    except KeyboardInterrupt:
        print("\n👋 Frontend server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Frontend server failed: {e}")

def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        return False
    
    # Load environment variables
    load_dotenv()
    
    # Check AWS credentials
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION']
    for var in required_vars:
        if not os.getenv(var):
            print(f"❌ Missing environment variable: {var}")
            return False
    
    print("✅ AWS credentials configured")
    
    # Check if required files exist
    required_files = ['main.py', 'index.html']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Missing file: {file}")
            return False
    
    print("✅ Required files found")
    
    # Check if required packages are installed
    try:
        import amazon_transcribe
        import websockets
        import flask
        print("✅ Required packages installed")
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        return False
    
    return True

def main():
    """Main function"""
    print("🏥 Med Coach - Complete Application Startup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('main.py'):
        print("❌ Please run this script from the project root directory.")
        sys.exit(1)
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Requirements check failed. Please fix the issues above.")
        sys.exit(1)
    
    print("\n✅ All requirements met!")
    
    # Show what will be started
    print("\n📋 Starting services:")
    print("  • Backend (Flask + WebSocket): http://127.0.0.1:8080")
    print("  • Frontend (Static files): http://127.0.0.1:5001")
    print("  • WebSocket server: ws://localhost:18765")
    
    print("\n⚠️  Important:")
    print("  • Make sure ports 8080, 5001, and 18765 are available")
    print("  • Allow microphone access when prompted by browser")
    print("  • Use Ctrl+C to stop all services")
    
    input("\nPress Enter to start all services...")
    
    try:
        # Start backend in a separate thread
        backend_thread = threading.Thread(target=start_backend)
        backend_thread.daemon = True
        backend_thread.start()
        
        # Wait a moment for backend to start
        print("\n⏳ Waiting for backend to start...")
        time.sleep(3)
        
        # Open browser
        print("🌐 Opening browser...")
        webbrowser.open('http://127.0.0.1:5001')
        
        # Start frontend (this will block)
        start_frontend()
        
    except KeyboardInterrupt:
        print("\n\n👋 All services stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting services: {e}")

if __name__ == "__main__":
    main()
