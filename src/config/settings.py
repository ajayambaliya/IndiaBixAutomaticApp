"""
Configuration settings for the PDF Generator
"""
import os
from pathlib import Path
from typing import Dict, Any

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src"
TEMPLATE_DIR = SRC_DIR / "templates"
STATIC_DIR = SRC_DIR / "static"
OUTPUT_DIR = SRC_DIR / "output"

# Ensure directories exist
for directory in [TEMPLATE_DIR, STATIC_DIR, OUTPUT_DIR, STATIC_DIR / "images"]:
    directory.mkdir(parents=True, exist_ok=True)

# Static asset paths
CSS_DIR = STATIC_DIR / "css"
FONTS_DIR = STATIC_DIR / "fonts"
IMAGES_DIR = STATIC_DIR / "images"
ICONS_DIR = STATIC_DIR / "icons"

# PDF Generation settings
PDF_CONFIG = {
    "format": "A4",
    "margin": {
        "top": "0.5in",
        "right": "0.5in",
        "bottom": "0.5in",
        "left": "0.5in"
    },
    "printBackground": True,
    "preferCSSPageSize": True
}

# CSS files for WeasyPrint
CSS_FILES = [
    str(CSS_DIR / "base.css"),
    str(CSS_DIR / "cover.css"),
    str(CSS_DIR / "content.css"),
    str(CSS_DIR / "components.css"),
    str(CSS_DIR / "print.css")
]

# Default Telegram channels
DEFAULT_ENGLISH_CHANNEL = "@daily_current_all_source"
DEFAULT_GUJARATI_CHANNEL = "@currentadda"

# Branding configuration
BRANDING = {
    "title": "Current Affairs Quiz",
    "logo": str(IMAGES_DIR / "logo.png"),
    "channels": {
        "english": os.getenv("ENGLISH_CHANNEL", DEFAULT_ENGLISH_CHANNEL),
        "gujarati": os.getenv("GUJARATI_CHANNEL", DEFAULT_GUJARATI_CHANNEL)
    },
    "join_link": {
        "english": f"https://t.me/{os.getenv('ENGLISH_CHANNEL', DEFAULT_ENGLISH_CHANNEL).replace('@', '')}",
        "gujarati": f"https://t.me/{os.getenv('GUJARATI_CHANNEL', DEFAULT_GUJARATI_CHANNEL).replace('@', '')}"
    },
    "copyright": f"© {os.getenv('COPYRIGHT_YEAR', '2023')} Current Adda by Ajay Ambaliya. All rights reserved.",
    "colors": {
        "primary": "#3b82f6",
        "secondary": "#8b5cf6",
        "accent": "#10b981"
    }
}

# MongoDB configuration - use None as default to handle missing env var gracefully
MONGO_DB_URI = os.getenv("MONGO_DB_URI")

# Telegram configuration - use None as default to handle missing env var gracefully
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ENGLISH_CHANNEL = os.getenv("ENGLISH_CHANNEL", DEFAULT_ENGLISH_CHANNEL)
GUJARATI_CHANNEL = os.getenv("GUJARATI_CHANNEL", DEFAULT_GUJARATI_CHANNEL)

# Author information
AUTHOR = {
    "name": "Ajay Ambaliya",
    "title": "Founder, Current Adda",
    "contact": "https://t.me/currentadda",
    "email": "ajay.ambaliya007@gmail.com"
}

# Template configuration
TEMPLATES = {
    "base": "base.html",
    "cover": "cover_page.html",
    "content": "content_page.html",
    "footer": "footer.html",
    "promotion": "promotion.html"
}

# Translation settings
TRANSLATION_ENABLED = True

# Main configuration dictionary
CONFIG = {
    "base_dir": str(BASE_DIR),
    "template_dir": str(TEMPLATE_DIR),
    "static_dir": str(STATIC_DIR),
    "output_dir": str(OUTPUT_DIR),
    "css_dir": str(CSS_DIR),
    "fonts_dir": str(FONTS_DIR),
    "images_dir": str(IMAGES_DIR),
    "icons_dir": str(ICONS_DIR),
    "pdf_config": PDF_CONFIG,
    "css_files": CSS_FILES,
    "branding": BRANDING,
    "templates": TEMPLATES,
    "mongo_db_uri": MONGO_DB_URI,
    "telegram_bot_token": TELEGRAM_BOT_TOKEN,
    "english_channel": ENGLISH_CHANNEL,
    "gujarati_channel": GUJARATI_CHANNEL,
    "author": AUTHOR,
    "translation_enabled": TRANSLATION_ENABLED
} 