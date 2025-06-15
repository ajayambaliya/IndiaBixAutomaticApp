#!/usr/bin/env python3
"""
Setup script for Current Adda PDF Generator
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required")
        sys.exit(1)
    print(f"✓ Python version: {sys.version.split()[0]}")

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("✓ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        sys.exit(1)

def install_playwright():
    """Install Playwright browsers"""
    print("Installing Playwright browsers...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install-deps"], check=True)
        print("✓ Playwright browsers installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error installing Playwright browsers: {e}")
        sys.exit(1)

def create_env_file(mongo_uri=None, telegram_token=None, english_channel=None, gujarati_channel=None):
    """Create .env file with configuration"""
    env_path = Path(".env")
    
    # Default values
    mongo_uri = mongo_uri or "mongodb://localhost:27017/"
    telegram_token = telegram_token or ""
    english_channel = english_channel or "@daily_current_all_source"
    gujarati_channel = gujarati_channel or "@currentadda"
    
    print("Creating .env file...")
    with open(env_path, "w") as f:
        f.write(f"MONGO_DB_URI={mongo_uri}\n")
        f.write(f"TELEGRAM_BOT_TOKEN={telegram_token}\n")
        f.write(f"ENGLISH_CHANNEL={english_channel}\n")
        f.write(f"GUJARATI_CHANNEL={gujarati_channel}\n")
    
    print(f"✓ Created .env file at {env_path.absolute()}")

def create_directories():
    """Create necessary directories"""
    dirs = [
        "src/output",
        "src/static/css",
        "src/static/fonts",
        "src/static/images",
        "src/static/icons"
    ]
    
    print("Creating directories...")
    for dir_path in dirs:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {path}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Setup Current Adda PDF Generator')
    parser.add_argument('--mongo-uri', help='MongoDB connection URI')
    parser.add_argument('--telegram-token', help='Telegram Bot Token')
    parser.add_argument('--english-channel', help='English Telegram Channel ID (e.g., @daily_current_all_source)')
    parser.add_argument('--gujarati-channel', help='Gujarati Telegram Channel ID (e.g., @currentadda)')
    parser.add_argument('--skip-dependencies', action='store_true', help='Skip installing dependencies')
    parser.add_argument('--skip-playwright', action='store_true', help='Skip installing Playwright browsers')
    return parser.parse_args()

def main():
    """Main entry point"""
    print("Setting up Current Adda PDF Generator...")
    args = parse_arguments()
    
    check_python_version()
    
    if not args.skip_dependencies:
        install_dependencies()
    
    if not args.skip_playwright:
        install_playwright()
    
    create_directories()
    create_env_file(
        args.mongo_uri, 
        args.telegram_token, 
        args.english_channel, 
        args.gujarati_channel
    )
    
    print("\nSetup completed successfully!")
    print("\nTo run the PDF generator:")
    print("  python main.py")
    print("\nTo send PDFs to Telegram:")
    print("  python main.py --send-telegram")
    print("\nTo run with specific options:")
    print("  python main.py --date YYYY-MM-DD")

if __name__ == "__main__":
    main() 