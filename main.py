#!/usr/bin/env python3
"""
Modern PDF Generator for Current Affairs
Created by Ajay Ambaliya for Current Adda
"""
import os
import asyncio
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import sys
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()

# Add the current directory to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import core modules
from src.core.scraper import AsyncDataScraper
from src.core.pdf_generator import ModernPDFGenerator
from src.core.template_manager import TemplateManager
from src.core.translator import translate_content, translate_with_mistral_api, is_primarily_gujarati
from src.core.utils import (
    generate_qr_code, 
    ensure_dir_exists, 
    validate_pdf,
    setup_mongodb_connection,
    get_processed_urls
)
from src.core.telegram_bot import send_pdfs_to_channel, TelegramPDFBot
from src.config.settings import CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('pdf_generator.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def generate_qr_codes(config: Dict[str, Any]) -> Dict[str, str]:
    """Generate QR codes for Telegram channels"""
    output_dir = Path(config['static_dir']) / 'images'
    ensure_dir_exists(output_dir)
    
    qr_codes = {}
    
    # English channel QR code
    english_channel = config['branding']['channels']['english']
    english_link = f"https://t.me/{english_channel.replace('@', '')}"
    english_qr_path = output_dir / "qr-english.png"
    qr_codes['english_qr'] = generate_qr_code(english_link, str(english_qr_path))
    
    # Gujarati channel QR code
    gujarati_channel = config['branding']['channels']['gujarati']
    gujarati_link = f"https://t.me/{gujarati_channel.replace('@', '')}"
    gujarati_qr_path = output_dir / "qr-gujarati.png"
    qr_codes['gujarati_qr'] = generate_qr_code(gujarati_link, str(gujarati_qr_path))
    
    return qr_codes


def prepare_data_for_template(data: List[Dict[str, Any]], language: str = "en") -> Dict[str, Any]:
    """Prepare data for template with proper statistics"""
    if not data:
        return {}
    
    # Get date from first question
    date = data[0].get('date', 'Unknown Date')
    
    # Calculate statistics
    stats = {
        "difficulty": {"easy": 0, "medium": 0, "hard": 0},
        "categories": {},
        "total": len(data)
    }
    
    # Count by difficulty and category
    for question in data:
        difficulty = question.get('difficulty', 'medium')
        category = question.get('category', 'general')
        
        if difficulty not in stats["difficulty"]:
            stats["difficulty"][difficulty] = 0
        stats["difficulty"][difficulty] = stats["difficulty"][difficulty] + 1
        
        if category not in stats["categories"]:
            stats["categories"][category] = 0
        stats["categories"][category] = stats["categories"][category] + 1
    
    # Group questions by category
    categorized_questions = {}
    for i, question in enumerate(data):
        category = question.get('category', 'general')
        if category not in categorized_questions:
            categorized_questions[category] = []
            
        # Add index to question for template reference
        question_copy = question.copy()
        question_copy['index'] = i + 1
        
        # Ensure options are in the correct format for the template
        if 'options' in question_copy and isinstance(question_copy['options'], list):
            # Convert list options to dictionary format expected by template
            options_dict = {}
            for j, option_text in enumerate(question_copy['options']):
                option_key = f"option_{chr(97 + j)}"  # a, b, c, d...
                options_dict[option_key] = option_text
            question_copy['options'] = options_dict
            
            # Determine correct answer key
            correct_answer = question_copy.get('correct_answer', '')
            if correct_answer.isalpha():
                question_copy['correct_answer_key'] = correct_answer.upper()
            elif correct_answer.isdigit() and 0 <= int(correct_answer) < len(question_copy['options']):
                question_copy['correct_answer_key'] = chr(65 + int(correct_answer))  # A, B, C, D...
        
        # Rename fields to match template expectations
        if 'question' in question_copy:
            question_copy['question_text'] = question_copy.pop('question')
        
        if 'explanation' not in question_copy:
            question_copy['explanation'] = "No explanation provided."
            
        categorized_questions[category].append(question_copy)
    
    # Prepare final data structure
    pdf_data = {
        "title": f"Current Affairs Quiz - {date}",
        "date": date,
        "language": language,
        "stats": stats,
        "categorized_questions": categorized_questions,
        "branding": CONFIG.get("branding", {}),
        "total_questions": len(data)
    }
    
    return pdf_data


async def process_and_generate_pdfs(
    date: Optional[str] = None,
    month: Optional[str] = None,
    date_range: Optional[Tuple[str, str]] = None,
    specific_url: Optional[str] = None,
    languages: List[str] = ["en", "gu"],
    github_actions_mode: bool = False,
    only_generate: bool = False
) -> Dict[str, List[str]]:
    """Process current affairs data and generate PDFs
    
    Args:
        date: Optional specific date to process
        month: Optional specific month to process
        date_range: Optional date range to process
        specific_url: Optional specific URL to process
        languages: List of languages to generate PDFs for
        github_actions_mode: Whether to run in GitHub Actions mode
        only_generate: Whether to only generate PDFs without scraping
        
    Returns:
        Dictionary mapping language codes to lists of PDF file paths
    """
    try:
        # Initialize output files dictionary
        output_files = {lang: [] for lang in languages}
        
        # Generate QR codes for Telegram channels
        qr_codes = {}
        
        if "en" in languages:
            english_qr_path = str(CONFIG['static_dir']) + "/images/qr-english.png"
            english_channel_link = CONFIG['branding']['join_link']['english']
            generate_qr_code(english_channel_link, english_qr_path)
            qr_codes['english_qr'] = english_qr_path
            logger.info(f"Generated QR code for {english_channel_link} at {english_qr_path}")
            
        if "gu" in languages:
            gujarati_qr_path = str(CONFIG['static_dir']) + "/images/qr-gujarati.png"
            gujarati_channel_link = CONFIG['branding']['join_link']['gujarati']
            generate_qr_code(gujarati_channel_link, gujarati_qr_path)
            qr_codes['gujarati_qr'] = gujarati_qr_path
            logger.info(f"Generated QR code for {gujarati_channel_link} at {gujarati_qr_path}")
        
        # Initialize PDF generator
        pdf_generator = ModernPDFGenerator(CONFIG)
        
        # If only_generate flag is set, skip scraping
        if only_generate:
            # Load questions from local storage
            logger.info("Only generate mode: Loading questions from local storage")
            # TODO: Implement loading from local storage
            return output_files
        
        # Fetch questions from IndiaBix
        logger.info("Fetching current affairs questions...")
        
        # Initialize scraper with MongoDB connection if available
        mongo_uri = CONFIG.get('mongo_db_uri')
        if not mongo_uri:
            logger.warning("MongoDB URI not provided, using local storage")
        
        # Setup MongoDB connection
        mongo_data = setup_mongodb_connection(mongo_uri)
        
        # Initialize scraper
        scraper = AsyncDataScraper(mongo_uri)
        
        # Fetch questions based on parameters
        if github_actions_mode:
            logger.info("Running in GitHub Actions mode - fetching all new URLs for current month")
            questions = await scraper.fetch_all_questions(
                specific_date=date,
                specific_month=month,
                date_range=date_range,
                specific_url=specific_url,
                force_process=False  # In GitHub Actions mode, we want to skip already processed URLs
            )
        else:
            questions = await scraper.fetch_all_questions(
                specific_date=date,
                specific_month=month,
                date_range=date_range,
                specific_url=specific_url,
                force_process=False  # Default behavior - skip already processed URLs
            )
        
        if not questions:
            logger.warning("No questions found!")
            return output_files
        
        # Group questions by date
        questions_by_date = {}
        for question in questions:
            question_date = question.get('date')
            if question_date not in questions_by_date:
                questions_by_date[question_date] = []
            questions_by_date[question_date].append(question)
        
        # Generate PDFs for each date
        for date, date_questions in questions_by_date.items():
            logger.info(f"Generating PDFs for date: {date} with {len(date_questions)} questions")
            
            # English PDF (if requested)
            if "en" in languages:
                logger.info(f"Generating English PDF for date: {date}")
                
                # Prepare data for template
                en_pdf_data = prepare_data_for_template(date_questions, "en")
                
                # Add QR code and metadata
                en_pdf_data.update({"english_qr": qr_codes.get('english_qr', '')})
                en_pdf_data['generation_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                en_pdf_data['source'] = "IndiaBix"  # Adding source attribution
                en_output_filename = f"current_affairs_{date}_en.pdf"
                
                try:
                    # Call generate_pdf with the correct parameters
                    en_output_path = await pdf_generator.generate_pdf(
                        template_name=CONFIG['templates']['base'],
                        data=en_pdf_data,
                        output_filename=en_output_filename
                    )
                    
                    if validate_pdf(en_output_path):
                        logger.info(f"Successfully generated English PDF: {en_output_path}")
                        output_files["en"].append(en_output_path)
                    else:
                        logger.error(f"Failed to validate English PDF: {en_output_path}")
                except Exception as e:
                    logger.error(f"Error generating English PDF: {e}")
            
            # Gujarati PDF (if requested)
            if "gu" in languages:
                logger.info(f"Generating Gujarati PDF for date: {date}")
                
                # Prepare data for template
                gu_pdf_data = prepare_data_for_template(date_questions, "gu")
                
                # Check if translation API key is available
                mistral_api_key = os.environ.get("MISTRAL_API_KEY")
                if not mistral_api_key:
                    logger.warning("MISTRAL_API_KEY not found. Skipping translation and generating Gujarati PDF with English content.")
                    # Just set the language to Gujarati but keep English content
                    gu_pdf_data["language"] = "gu"
                else:
                    # Translate content if translation is enabled and API key is available
                    if CONFIG.get('translation_enabled', True):
                        logger.info("Translating content to Gujarati...")
                        try:
                            # Add a delay before starting translation to ensure API rate limits
                            await asyncio.sleep(2)
                            
                            # First translate the title and important metadata
                            if 'title' in gu_pdf_data and isinstance(gu_pdf_data['title'], str):
                                gu_pdf_data['title'] = await translate_with_mistral_api(gu_pdf_data['title'], "gu")
                            
                            # Then translate the full content
                            gu_pdf_data = await translate_content(gu_pdf_data, "gu")
                            
                            # Verify translation quality for key fields
                            translation_verification_fields = ['title']
                            
                            # Also check a sample of questions for quality
                            if 'categorized_questions' in gu_pdf_data and isinstance(gu_pdf_data['categorized_questions'], dict):
                                for category, questions in gu_pdf_data['categorized_questions'].items():
                                    if isinstance(questions, list) and questions:
                                        # Check the first question in each category
                                        if 'question_text' in questions[0]:
                                            translation_verification_fields.append(f"question_text_in_{category}")
                                            # Store the question text for verification
                                            gu_pdf_data[f"question_text_in_{category}"] = questions[0]['question_text']
                            
                            # Verify each field and retranslate if needed
                            for field_name in translation_verification_fields:
                                if field_name in gu_pdf_data and isinstance(gu_pdf_data[field_name], str):
                                    field_text = gu_pdf_data[field_name]
                                    
                                    # Check if the field appears to still be in English
                                    if field_text.isascii() or not is_primarily_gujarati(field_text):
                                        logger.warning(f"Field '{field_name}' appears to not be properly translated to Gujarati. Attempting to retranslate.")
                                        await asyncio.sleep(3)  # Additional delay before retry
                                        
                                        # Try retranslation with a more forceful prompt
                                        retranslated_text = await translate_with_mistral_api(field_text, "gu")
                                        
                                        # Update the field if retranslation succeeded
                                        if retranslated_text and is_primarily_gujarati(retranslated_text):
                                            logger.info(f"Successfully retranslated field '{field_name}'")
                                            gu_pdf_data[field_name] = retranslated_text
                                            
                                            # If this is a question_text field, update it in the categorized_questions as well
                                            if field_name.startswith("question_text_in_"):
                                                category = field_name.replace("question_text_in_", "")
                                                if category in gu_pdf_data['categorized_questions'] and gu_pdf_data['categorized_questions'][category]:
                                                    gu_pdf_data['categorized_questions'][category][0]['question_text'] = retranslated_text
                            
                            # Clean up temporary verification fields
                            for field_name in list(gu_pdf_data.keys()):
                                if field_name.startswith("question_text_in_"):
                                    del gu_pdf_data[field_name]
                                    
                        except Exception as e:
                            logger.error(f"Error translating content to Gujarati: {e}")
                            logger.warning("Continuing with English content but Gujarati language setting.")
                
                # Add QR code and metadata
                gu_pdf_data.update({"gujarati_qr": qr_codes.get('gujarati_qr', '')})
                gu_pdf_data['generation_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                gu_pdf_data['source'] = "IndiaBix"  # Adding source attribution
                gu_output_filename = f"current_affairs_{date}_gu.pdf"
                
                try:
                    # Call generate_pdf with the correct parameters
                    gu_output_path = await pdf_generator.generate_pdf(
                        template_name=CONFIG['templates']['base'],
                        data=gu_pdf_data,
                        output_filename=gu_output_filename
                    )
                    
                    if validate_pdf(gu_output_path):
                        logger.info(f"Successfully generated Gujarati PDF: {gu_output_path}")
                        output_files["gu"].append(gu_output_path)
                    else:
                        logger.error(f"Failed to validate Gujarati PDF: {gu_output_path}")
                except Exception as e:
                    logger.error(f"Error generating Gujarati PDF: {e}")
        
        return output_files
    
    except Exception as e:
        logger.error(f"Error in process_and_generate_pdfs: {e}")
        return {lang: [] for lang in languages}


async def send_pdfs_to_channels(pdf_files: Dict[str, List[str]], languages: List[str] = ["en", "gu"]) -> None:
    """Send PDFs to their respective Telegram channels
    
    Args:
        pdf_files: Dictionary mapping language codes to lists of PDF file paths
        languages: List of language codes to send PDFs for
    """
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN") or CONFIG.get('telegram_bot_token')
    
    if not telegram_token:
        logger.error("Telegram bot token not provided. Skipping Telegram upload.")
        logger.error("To enable Telegram uploads, set the TELEGRAM_BOT_TOKEN environment variable.")
        return
    
    try:
        bot = TelegramPDFBot(telegram_token)
        
        for lang in languages:
            if lang not in pdf_files or not pdf_files[lang]:
                continue
                
            # Get channel ID for the language
            if lang == "en":
                channel_id = os.getenv("ENGLISH_CHANNEL") or CONFIG.get('english_channel')
            elif lang == "gu":
                channel_id = os.getenv("GUJARATI_CHANNEL") or CONFIG.get('gujarati_channel')
            else:
                logger.warning(f"No channel configured for language: {lang}")
                continue
                
            # Send PDFs to the channel
            for pdf_path in pdf_files[lang]:
                await send_pdfs_to_channel(bot, channel_id, pdf_path)
                
    except Exception as e:
        logger.error(f"Error sending PDFs to channels: {e}")
        logger.error("Make sure TELEGRAM_BOT_TOKEN, ENGLISH_CHANNEL, and GUJARATI_CHANNEL environment variables are set correctly.")


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Generate Current Affairs PDFs')
    
    # Date options (mutually exclusive)
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument('--date', help='Specific date (YYYY-MM-DD)')
    date_group.add_argument('--date-range', nargs=2, metavar=('START_DATE', 'END_DATE'), 
                           help='Date range (YYYY-MM-DD YYYY-MM-DD)')
    date_group.add_argument('--month', help='Specific month (YYYY-MM)')
    date_group.add_argument('--url', help='Specific URL to scrape')
    
    # Language options
    parser.add_argument('--languages', nargs='+', choices=['en', 'gu'], default=['en', 'gu'],
                       help='Languages to generate PDFs for (default: en gu)')
    
    # Mode options
    parser.add_argument('--github-actions', action='store_true', 
                       help='Run in GitHub Actions mode (fetch all new URLs)')
    parser.add_argument('--only-generate', action='store_true',
                       help='Only generate PDFs without scraping new data')
    parser.add_argument('--send-telegram', action='store_true',
                       help='Send generated PDFs to Telegram channels')
    
    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Process date range if provided
    date_range = None
    if args.date_range:
        date_range = (args.date_range[0], args.date_range[1])
    
    # Process and generate PDFs
    pdf_files = await process_and_generate_pdfs(
        date=args.date,
        month=args.month,
        date_range=date_range,
        specific_url=args.url,
        languages=args.languages,
        github_actions_mode=args.github_actions,
        only_generate=args.only_generate
    )
    
    # Send PDFs to Telegram channels if requested
    if args.send_telegram:
        await send_pdfs_to_channels(pdf_files, args.languages)
    
    # Print summary
    total_pdfs = sum(len(files) for files in pdf_files.values())
    logger.info(f"Generated {total_pdfs} PDFs")
    
    for lang, files in pdf_files.items():
        for file in files:
            logger.info(f"- {lang}: {file}")


if __name__ == "__main__":
    asyncio.run(main()) 