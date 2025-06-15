"""
Utility functions for the PDF generator system
"""
import os
import logging
import qrcode
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
from datetime import datetime
import tempfile
import pymongo
from pymongo import MongoClient, errors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('utils.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def generate_qr_code(data: str, output_path: str, size: int = 10) -> str:
    """Generate a QR code for the given data and save it to the output path"""
    try:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        # Create an image from the QR Code instance
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save the image
        img.save(output_path)
        logger.info(f"Generated QR code for {data} at {output_path}")
        
        return output_path
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        return ""

def format_date(date_str: str, format_str: str = '%B %d, %Y') -> str:
    """Format a date string"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting date {date_str}: {e}")
        return date_str

def save_json_data(data: Dict[str, Any], output_path: str) -> bool:
    """Save data to JSON file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON data to {output_path}: {e}")
        return False

def load_json_data(input_path: str) -> Dict[str, Any]:
    """Load data from JSON file"""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON data from {input_path}: {e}")
        return {}

def ensure_dir_exists(directory: Path) -> None:
    """Ensure a directory exists, creating it if necessary"""
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)

def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error getting file size for {file_path}: {e}")
        return 0

def get_file_size_formatted(file_path: str) -> str:
    """Get file size in human-readable format"""
    size_bytes = get_file_size(file_path)
    
    # Format size
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024 or unit == 'GB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def validate_pdf(pdf_path: str) -> bool:
    """Validate that a PDF file exists and is not empty"""
    try:
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file does not exist: {pdf_path}")
            return False
            
        file_size = os.path.getsize(pdf_path)
        if file_size < 1000:  # Less than 1KB is probably not a valid PDF
            logger.error(f"PDF file is too small ({file_size} bytes): {pdf_path}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error validating PDF: {e}")
        return False

def setup_mongodb_connection(mongo_uri: str) -> Optional[Dict[str, Any]]:
    """Set up MongoDB connection and return database and collections"""
    try:
        if not mongo_uri:
            logger.warning("No MongoDB URI provided, continuing without database storage")
            return None
            
        # Set a short timeout to fail fast if the connection is not available
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000)
        
        # Test the connection
        try:
            client.admin.command('ping')  # A lighter command to test connection
        except pymongo.errors.ConnectionFailure as e:
            logger.warning(f"MongoDB connection failed: {e}. Continuing without database storage.")
            return None
        except Exception as e:
            logger.warning(f"MongoDB connection test failed: {e}. Continuing without database storage.")
            return None
        
        db = client['indiabixauto']
        processed_urls = db['scraped_urls']
        questions = db['questions']
        
        # Create indexes for faster lookups
        try:
            processed_urls.create_index("url", unique=True)
            questions.create_index([("date", 1), ("index", 1)])
        except Exception as e:
            logger.warning(f"Failed to create MongoDB indexes: {e}. Continuing with reduced performance.")
        
        logger.info("MongoDB connection successful")
        return {
            "client": client,
            "db": db,
            "processed_urls": processed_urls,
            "questions": questions
        }
    except pymongo.errors.ConfigurationError as e:
        logger.error(f"MongoDB configuration error: {e}. Continuing without database storage.")
        return None
    except pymongo.errors.ConnectionFailure as e:
        logger.error(f"MongoDB connection failed: {e}. Continuing without database storage.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}. Continuing without database storage.")
        return None

def get_processed_urls(mongo_uri: Optional[str] = None) -> Set[str]:
    """Get all previously processed URLs from MongoDB that had data"""
    if not mongo_uri:
        return set()
        
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client['indiabixauto']
        processed_urls_collection = db['scraped_urls']
        
        # Only get URLs that had data
        processed_urls = {doc["url"] for doc in processed_urls_collection.find(
            {"has_data": True}, 
            {"url": 1}
        )}
        logger.info(f"Found {len(processed_urls)} previously processed URLs with data in MongoDB")
        return processed_urls
    except Exception as e:
        logger.error(f"Error retrieving processed URLs from MongoDB: {e}")
        return set()

def mark_url_as_processed(mongo_connection: Optional[Dict[str, Any]], url: str, 
                         question_count: int = 0) -> bool:
    """Mark a URL as processed in MongoDB"""
    if not mongo_connection:
        return False
        
    try:
        # Using the processed_urls key from the mongo_connection dictionary
        result = mongo_connection["processed_urls"].update_one(
            {"url": url},
            {"$set": {
                "url": url,
                "processed_at": datetime.now(),
                "question_count": question_count,
                "has_data": question_count > 0
            }},
            upsert=True
        )
        logger.info(f"Marked URL as processed: {url} with {question_count} questions")
        return True
    except errors.PyMongoError as e:
        logger.error(f"Error marking URL as processed: {e}")
        return False

def store_questions(mongo_connection: Optional[Dict[str, Any]], questions: List[Dict[str, Any]]) -> bool:
    """Store questions in MongoDB"""
    if not mongo_connection or not questions:
        return False
        
    try:
        result = mongo_connection["questions"].insert_many(questions)
        logger.info(f"Stored {len(questions)} questions in the database")
        return True
    except errors.PyMongoError as e:
        logger.error(f"Error storing questions in MongoDB: {e}")
        return False 