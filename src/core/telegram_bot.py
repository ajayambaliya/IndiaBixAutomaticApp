"""
Telegram bot for sending PDFs to channels
"""
import os
import logging
import asyncio
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import PyPDF2

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('telegram_bot.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TelegramPDFBot:
    """Bot for sending PDFs to Telegram channels"""
    
    def __init__(self, token: str):
        """Initialize with bot token"""
        self.bot = Bot(token=token)
        
    async def send_pdf(self, 
                      channel_id: str, 
                      pdf_path: str, 
                      caption: Optional[str] = None) -> bool:
        """Send a PDF file to a Telegram channel"""
        try:
            if not os.path.exists(pdf_path):
                logger.error(f"PDF file not found: {pdf_path}")
                return False
                
            filename = os.path.basename(pdf_path)
            
            # Default caption if none provided
            if not caption:
                date_str = self._extract_date_from_filename(filename)
                question_count = self._count_questions_in_pdf(pdf_path)
                
                # Determine language from filename
                lang = "English"
                if "_gu.pdf" in filename:
                    lang = "Gujarati"
                elif "_hi.pdf" in filename:
                    lang = "Hindi"
                
                caption = self._create_beautiful_caption(date_str, lang, question_count, channel_id)
            
            logger.info(f"Sending PDF {filename} to channel {channel_id}")
            
            with open(pdf_path, 'rb') as pdf_file:
                await self.bot.send_document(
                    chat_id=channel_id,
                    document=pdf_file,
                    filename=filename,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN
                )
                
            logger.info(f"Successfully sent PDF {filename} to channel {channel_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error when sending PDF: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending PDF: {e}")
            return False
    
    def _create_beautiful_caption(self, date_str: str, language: str, question_count: int, channel_id: str) -> str:
        """Create a beautiful caption with emojis and formatting"""
        # Get channel name without @ symbol for URL
        channel_name = channel_id.replace('@', '')
        channel_url = f"https://t.me/{channel_name}"
        
        # Emojis for different sections
        date_emoji = "📅"
        lang_emoji = "🌐"
        questions_emoji = "❓"
        book_emoji = "📚"
        fire_emoji = "🔥"
        star_emoji = "⭐"
        rocket_emoji = "🚀"
        
        # Create the caption with sections
        caption = (
            f"{book_emoji} *CURRENT AFFAIRS QUIZ* {book_emoji}\n\n"
            f"{date_emoji} *Date:* {date_str}\n"
            f"{lang_emoji} *Language:* {language}\n"
            f"{questions_emoji} *Questions:* {question_count}+\n\n"
            f"{fire_emoji} *Daily updates for competitive exams*\n\n"
            f"{star_emoji} *WHY JOIN OUR CHANNEL?* {star_emoji}\n"
            f"• Daily Current Affairs Updates\n"
            f"• Free Study Material\n"
            f"• MCQs & Quizzes\n"
            f"• Exam Notifications\n\n"
            f"{rocket_emoji} *Join Now:* [{channel_id}]({channel_url})\n\n"
            f"_Curated by: Current Adda_"
        )
        
        return caption
    
    def _extract_date_from_filename(self, filename: str) -> str:
        """Extract and format date from filename"""
        # Extract YYYY-MM-DD pattern
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if date_match:
            date_str = date_match.group(1)
            try:
                # Convert to more readable format
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%B %d, %Y')
            except:
                return date_str
        return "Unknown Date"
    
    def _count_questions_in_pdf(self, pdf_path: str) -> int:
        """Count the number of questions in a PDF"""
        try:
            # First try to extract from filename if it contains a number
            filename = os.path.basename(pdf_path)
            match = re.search(r'_(\d+)q_', filename)
            if match:
                return int(match.group(1))
            
            # Try to extract from PDF content
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    text = ""
                    # Get text from first few pages
                    for i in range(min(3, len(reader.pages))):
                        text += reader.pages[i].extract_text()
                    
                    # Look for patterns like "Total Questions: 15" or "Questions: 15"
                    matches = re.findall(r'(?:Total\s+Questions|Questions):\s*(\d+)', text)
                    if matches:
                        return int(matches[0])
                    
                    # Count occurrences of "Question" or "Q."
                    question_count = len(re.findall(r'(?:Question\s+\d+|Q\.\s*\d+):', text))
                    if question_count > 0:
                        return question_count
            except:
                # If PDF reading fails, try a different approach
                pass
                
            # If we can't determine, estimate based on file size
            # Rough estimate: 1 question ≈ 5 KB
            file_size_kb = os.path.getsize(pdf_path) / 1024
            estimated_questions = max(int(file_size_kb / 5), 1)
            
            # Cap at a reasonable number
            return min(estimated_questions, 30)
            
        except Exception as e:
            logger.error(f"Error counting questions: {e}")
            return 10  # Default fallback
            
    async def send_announcement(self, 
                              channel_id: str, 
                              title: str, 
                              message: str) -> bool:
        """Send an announcement message to a Telegram channel"""
        try:
            # Get channel name without @ symbol for URL
            channel_name = channel_id.replace('@', '')
            channel_url = f"https://t.me/{channel_name}"
            
            # Create a beautiful formatted message
            full_message = (
                f"📢 *{title}* 📢\n\n"
                f"{message}\n\n"
                f"🔔 *Stay Updated:* [{channel_id}]({channel_url})\n"
                f"📚 *Curated by:* Current Adda"
            )
            
            await self.bot.send_message(
                chat_id=channel_id,
                text=full_message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Successfully sent announcement to channel {channel_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error when sending announcement: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending announcement: {e}")
            return False
            
    async def send_pdf_batch(self, 
                           channel_id: str, 
                           pdf_files: List[str],
                           announcement: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Send a batch of PDFs to a Telegram channel with optional announcement"""
        results = {
            "success": 0,
            "failed": 0,
            "files": []
        }
        
        # Send announcement if provided
        if announcement and announcement.get("title") and announcement.get("message"):
            announcement_sent = await self.send_announcement(
                channel_id, 
                announcement["title"], 
                announcement["message"]
            )
            results["announcement_sent"] = announcement_sent
        
        # If no PDFs to send, return early
        if not pdf_files:
            logger.warning("No PDF files provided to send")
            return results
            
        # Send each PDF
        for pdf_path in pdf_files:
            try:
                filename = os.path.basename(pdf_path)
                date_str = self._extract_date_from_filename(filename)
                
                # Determine language from filename
                lang = "English"
                if "_gu.pdf" in filename:
                    lang = "Gujarati"
                elif "_hi.pdf" in filename:
                    lang = "Hindi"
                
                # Count questions
                question_count = self._count_questions_in_pdf(pdf_path)
                
                # Create a beautiful caption
                caption = self._create_beautiful_caption(date_str, lang, question_count, channel_id)
                
                success = await self.send_pdf(channel_id, pdf_path, caption)
                
                if success:
                    results["success"] += 1
                    results["files"].append({"path": pdf_path, "status": "sent"})
                else:
                    results["failed"] += 1
                    results["files"].append({"path": pdf_path, "status": "failed"})
                    
                # Add a small delay between sends to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing PDF {pdf_path}: {e}")
                results["failed"] += 1
                results["files"].append({"path": pdf_path, "status": "error", "error": str(e)})
                
        return results


async def send_pdfs_to_channel(bot_or_token, channel_id: str, pdf_path: str) -> bool:
    """Send a PDF to a Telegram channel
    
    Args:
        bot_or_token: Either a TelegramPDFBot instance or a bot token string
        channel_id: The ID of the Telegram channel to send to
        pdf_path: Path to the PDF file to send
        
    Returns:
        True if the PDF was sent successfully, False otherwise
    """
    try:
        # Check if bot_or_token is a string (token) or a TelegramPDFBot instance
        if isinstance(bot_or_token, str):
            bot = TelegramPDFBot(bot_or_token)
        else:
            bot = bot_or_token
        
        # Check if the PDF file exists
        if not os.path.exists(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return False
        
        # Extract information from the PDF file path
        filename = os.path.basename(pdf_path)
        date_str = bot._extract_date_from_filename(filename)
        
        # Determine language from filename
        lang = "English"
        if "_gu.pdf" in filename:
            lang = "Gujarati"
        elif "_hi.pdf" in filename:
            lang = "Hindi"
        
        # Count questions
        question_count = bot._count_questions_in_pdf(pdf_path)
        
        # Create a beautiful caption
        caption = bot._create_beautiful_caption(date_str, lang, question_count, channel_id)
        
        # Send the PDF
        success = await bot.send_pdf(channel_id, pdf_path, caption)
        return success
    except Exception as e:
        logger.error(f"Error sending PDF to channel: {e}")
        return False


async def send_pdfs_from_directory(token: str, channel_id: str, pdf_dir: str) -> None:
    """Send all PDFs in a directory to a Telegram channel"""
    bot = TelegramPDFBot(token)
    
    # Get all PDF files in the directory
    pdf_files = [str(f) for f in Path(pdf_dir).glob("*.pdf")]
    
    if not pdf_files:
        logger.warning(f"No PDF files found in directory: {pdf_dir}")
        await bot.send_announcement(
            channel_id,
            "No Current Affairs Updates",
            f"No new current affairs found for {datetime.now().strftime('%Y-%m-%d')}"
        )
        return
        
    # Create announcement
    announcement = {
        "title": f"📚 Current Affairs Update - {datetime.now().strftime('%B %d, %Y')}",
        "message": f"Fresh current affairs PDFs are ready! Check them out below.\n\n"
                  f"Total PDFs: {len(pdf_files)}\n"
                  f"Join @currentadda for daily updates!"
    }
    
    # Send PDFs
    results = await bot.send_pdf_batch(channel_id, pdf_files, announcement)
    
    logger.info(f"PDF sending results: {results['success']} successful, {results['failed']} failed")


if __name__ == "__main__":
    # Example usage
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TELEGRAM_CHANNEL", "@currentadda")
    pdf_dir = os.environ.get("PDF_DIR", "src/output")
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
    else:
        asyncio.run(send_pdfs_from_directory(token, channel, pdf_dir)) 