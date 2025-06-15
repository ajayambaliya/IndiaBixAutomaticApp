#!/usr/bin/env python3
"""
Modern PDF Generator - Async Data Scraper
Created by Ajay Ambaliya for Current Adda
"""
import os
import re
import sys
import json
import aiohttp
import asyncio
import logging
import calendar
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime as dt, timedelta
from bs4 import BeautifulSoup, Tag
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from src.core.utils import setup_mongodb_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scraper.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

class AsyncDataScraper:
    """
    Asynchronous data scraper for fetching current affairs questions from IndiaBix
    """
    
    def __init__(self, mongo_uri: Optional[str] = None):
        """
        Initialize the scraper with optional MongoDB connection
        
        Args:
            mongo_uri: MongoDB connection URI (optional)
        """
        self.mongo_uri = mongo_uri
        self.db = None
        self.processed_urls_collection = None
        self.questions_collection = None
        
        # Set up MongoDB connection if URI is provided
        if mongo_uri:
            try:
                # Initialize MongoDB connection
                mongo_data = setup_mongodb_connection(mongo_uri)
                if mongo_data is not None:
                    logger.info("MongoDB connection established")
                    self.db = mongo_data.get("db")
                    self.processed_urls_collection = mongo_data.get("processed_urls")
                    self.questions_collection = mongo_data.get("questions")
            except Exception as e:
                logger.error(f"Error connecting to MongoDB: {e}")
                # Continue without database
    
    def get_processed_urls(self) -> Set[str]:
        """
        Get set of already processed URLs that had data
        
        Returns:
            Set of URLs that have already been processed and had data
        """
        processed_urls = set()
        
        # If MongoDB is not connected, return empty set
        if self.processed_urls_collection is None:
            return processed_urls
        
        try:
            # Get only processed URLs that had data
            cursor = self.processed_urls_collection.find(
                {"has_data": True}, 
                {"url": 1, "_id": 0}
            )
            for doc in cursor:
                processed_urls.add(doc["url"])
                
            logger.info(f"Found {len(processed_urls)} previously processed URLs with data")
        except Exception as e:
            logger.error(f"Error getting processed URLs: {e}")
        
        return processed_urls
    
    @staticmethod
    def clean_html_text(text: str) -> str:
        """
        Clean HTML text by removing extra whitespace and HTML tags
        
        Args:
            text: HTML text to clean
            
        Returns:
            Cleaned text
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]*>', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    async def fetch_url(self, url: str, session: aiohttp.ClientSession) -> str:
        """
        Fetch a URL using aiohttp
        
        Args:
            url: URL to fetch
            session: aiohttp ClientSession
            
        Returns:
            HTML content
        """
        try:
            # Use the existing session which should already have SSL verification disabled
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(f"Error fetching URL {url}: {response.status}")
                    return ""
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return ""
    
    def extract_question_data(self, html_content: str, url: str) -> List[Dict[str, Any]]:
        """
        Extract question data from HTML content
        
        Args:
            html_content: HTML content
            url: URL of the page
            
        Returns:
            List of extracted questions
        """
        if not html_content:
            return []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract date from URL
            date_match = re.search(r'/current-affairs/(\d{4}-\d{2}-\d{2})/', url)
            if not date_match:
                logger.error(f"Could not extract date from URL: {url}")
                return []
            
            date = date_match.group(1)
            
            # Get all questions
            questions_data = []
            
            # Find all question blocks with the new structure
            question_blocks = soup.find_all('div', class_='bix-div-container')
            
            if not question_blocks:
                logger.warning(f"No question blocks found for URL: {url}")
                return []
            
            logger.info(f"Found {len(question_blocks)} questions for date: {date}")
            
            for i, block in enumerate(question_blocks, 1):
                try:
                    # Extract question text from the new structure
                    question_element = block.find('div', class_='bix-td-qtxt')
                    if not question_element:
                        continue
                    
                    question_text = self.clean_html_text(str(question_element))
                    
                    # Extract options from the new structure
                    options = []
                    options_element = block.find('div', class_='bix-tbl-options')
                    
                    if options_element:
                        option_rows = options_element.find_all('div', class_='bix-opt-row')
                        for option_row in option_rows:
                            option_value = option_row.find('div', class_='bix-td-option-val')
                            if option_value:
                                option_text = self.clean_html_text(str(option_value))
                                options.append(option_text)
                    
                    # Extract correct answer from the new structure
                    correct_answer = ""
                    hidden_answer = block.find('input', {'id': lambda x: x and x.startswith('hdnAnswer_')})
                    
                    if hidden_answer and 'value' in hidden_answer.attrs:
                        correct_answer = hidden_answer['value']
                    
                    # Extract explanation from the new structure
                    explanation = ""
                    explanation_element = block.find('div', class_='bix-ans-description')
                    
                    if explanation_element:
                        explanation = self.clean_html_text(str(explanation_element))
                    
                    # Extract category from the new structure
                    category = "general"
                    category_element = block.find('div', class_='explain-link')
                    if category_element:
                        category_text = self.clean_html_text(str(category_element))
                        category_match = re.search(r'Category\s*:\s*([^<]+)', category_text)
                        if category_match:
                            category = category_match.group(1).strip().lower()
                    
                    # Determine difficulty based on explanation length and complexity
                    difficulty = self._determine_difficulty(explanation, question_text)
                    
                    # Create question object
                    question_data = {
                        "id": f"{date}-{i}",
                        "date": date,
                        "question": question_text,
                        "options": options,
                        "correct_answer": correct_answer,
                        "explanation": explanation,
                        "difficulty": difficulty,
                        "category": category,
                        "url": url
                    }
                    
                    questions_data.append(question_data)
                    
                except Exception as e:
                    logger.error(f"Error extracting question data: {e}")
                    continue
            
            logger.info(f"Extracted {len(questions_data)} questions from URL: {url}")
            
            return questions_data
            
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            return []
    
    def _determine_difficulty(self, explanation: str, question: str) -> str:
        """
        Determine the difficulty of a question based on its explanation and content
        
        Args:
            explanation: Question explanation
            question: Question text
            
        Returns:
            Difficulty level: easy, medium, or hard
        """
        # Determine difficulty based on explanation length and complexity
        if len(explanation) < 100:
            return "easy"
        elif len(explanation) < 300:
            return "medium"
        else:
            return "hard"
    
    def _determine_category(self, question: str) -> str:
        """
        Determine the category of a question based on its content
        
        Args:
            question: Question text
            
        Returns:
            Category: science, sports, politics, etc.
        """
        question = question.lower()
        
        # Define categories and their keywords
        categories = {
            "science": ["science", "scientist", "discovery", "invention", "technology", "research", "nasa", "space"],
            "sports": ["sport", "cricket", "football", "hockey", "tennis", "player", "tournament", "championship", "olympics"],
            "politics": ["politic", "minister", "government", "election", "party", "president", "prime minister", "parliament"],
            "economy": ["economy", "economic", "finance", "market", "stock", "trade", "business", "gdp", "fiscal", "monetary"],
            "awards": ["award", "prize", "medal", "honor", "recognition", "winner", "recipient"],
            "defense": ["defense", "military", "army", "navy", "air force", "weapon", "missile", "security"],
            "international": ["international", "global", "world", "un", "united nations", "treaty", "agreement", "foreign"]
        }
        
        # Check if the question contains any category keywords
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in question:
                    return category
        
        # Default category
        return "general"
    
    async def process_url(self, url: str, session: aiohttp.ClientSession, processed_urls: Set[str], force_process: bool = False) -> List[Dict[str, Any]]:
        """
        Process a URL to extract questions
        
        Args:
            url: URL to process
            session: aiohttp ClientSession
            processed_urls: Set of already processed URLs
            force_process: Whether to force processing even if the URL has been processed before
            
        Returns:
            List of extracted questions
        """
        if not force_process and url in processed_urls:
            logger.info(f"URL already processed: {url}")
            return []
        
        try:
            # Fetch URL content using the provided session
            html_content = await self.fetch_url(url, session)
            if not html_content:
                logger.warning(f"No content found at URL: {url}")
                return []
            
            # Extract questions
            questions = self.extract_question_data(html_content, url)
            
            # Only store questions and mark URL as processed if questions were found
            if questions:
                logger.info(f"Found {len(questions)} questions at URL: {url}")
                
                # Store questions in database if MongoDB is connected
                if self.questions_collection is not None:
                    for question in questions:
                        try:
                            self.questions_collection.update_one(
                                {"id": question["id"]},
                                {"$set": question},
                                upsert=True
                            )
                        except Exception as e:
                            logger.error(f"Error storing question in database: {e}")
                
                # Mark URL as processed if MongoDB is connected
                if self.processed_urls_collection is not None:
                    try:
                        self.processed_urls_collection.update_one(
                            {"url": url},
                            {"$set": {
                                "url": url, 
                                "processed_at": dt.now(),
                                "question_count": len(questions),
                                "has_data": True
                            }},
                            upsert=True
                        )
                        logger.info(f"Marked URL as processed: {url} with {len(questions)} questions")
                    except Exception as e:
                        logger.error(f"Error marking URL as processed: {e}")
            else:
                logger.warning(f"No questions found at URL: {url}")
                # Do not mark URLs without data as processed, so they will be retried on future runs
            
            return questions
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            return []
    
    def _is_date_in_range(self, date_str: str, start_date: str, end_date: str) -> bool:
        """Check if a date is within a specified range"""
        date_obj = dt.strptime(date_str, "%Y-%m-%d")
        start_obj = dt.strptime(start_date, "%Y-%m-%d")
        end_obj = dt.strptime(end_date, "%Y-%m-%d")
        
        return start_obj <= date_obj <= end_obj
    
    async def process_specific_url(self, url: str, force_process: bool = False) -> List[Dict[str, Any]]:
        """
        Process a specific URL
        
        Args:
            url: The URL to process
            force_process: Whether to force processing even if the URL has been processed before
            
        Returns:
            List of extracted questions
        """
        processed_urls = self.get_processed_urls()
        
        # Create a session with SSL verification disabled
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            questions = await self.process_url(url, session, processed_urls, force_process)
        
        return questions
    
    async def fetch_all_questions(
        self, 
        specific_date: str = None, 
        specific_month: str = None,
        date_range: Tuple[str, str] = None,
        specific_url: str = None,
        force_process: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch all questions based on criteria
        
        Args:
            specific_date: Optional specific date to fetch (format: YYYY-MM-DD)
            specific_month: Optional specific month to fetch (format: YYYY-MM)
            date_range: Optional tuple of (start_date, end_date) for date range (format: YYYY-MM-DD)
            specific_url: Optional specific URL to fetch
            force_process: Whether to force processing of all URLs even if they've been processed before
            
        Returns:
            List of all questions matching the criteria
        """
        try:
            all_questions = []
            
            # If specific URL is provided, process only that URL
            if specific_url:
                logger.info(f"Processing specific URL: {specific_url}")
                return await self.process_specific_url(specific_url, force_process)
            
            # Get already processed URLs
            processed_urls = self.get_processed_urls()
            urls_to_process = []
            skipped_urls = []
            
            # If specific date is provided, create URL for that date
            if specific_date:
                url = f"https://www.indiabix.com/current-affairs/{specific_date}/"
                if not force_process and url in processed_urls:
                    logger.info(f"Skipping already processed URL: {url}")
                    skipped_urls.append(url)
                else:
                    urls_to_process.append(url)
            else:
                # If specific month is provided, parse it
                if specific_month:
                    logger.info(f"Processing specific month: {specific_month}")
                    try:
                        year, month = map(int, specific_month.split('-'))
                    except:
                        logger.error(f"Invalid month format: {specific_month}, expected YYYY-MM")
                        return []
                else:
                    # Default to current month
                    today = dt.now()
                    year, month = today.year, today.month
                
                # Get the current date for limiting URL generation
                current_date = dt.now()
                
                # If the specified month is in the future or is the current month,
                # limit URL generation to the current date
                if (year > current_date.year or 
                    (year == current_date.year and month > current_date.month)):
                    logger.warning(f"Specified month {year}-{month:02d} is in the future. No URLs to process.")
                    return []
                elif (year == current_date.year and month == current_date.month):
                    # For current month, only generate URLs up to current day
                    last_day = current_date.day
                else:
                    # For past months, generate URLs for all days
                    try:
                        if month == 12:
                            next_month = dt(year + 1, 1, 1)
                        else:
                            next_month = dt(year, month + 1, 1)
                        last_day = (next_month - timedelta(days=1)).day
                    except:
                        # Fallback to calendar module
                        last_day = calendar.monthrange(year, month)[1]
                
                logger.info(f"Generating URLs for {year}-{month:02d} from day 1 to day {last_day}")
                
                # Generate URLs for each day in the month
                for day in range(1, last_day + 1):
                    url_date = f"{year}-{month:02d}-{day:02d}"
                    
                    # If specific_date is provided, only process that date
                    if specific_date and url_date != specific_date:
                        continue
                    
                    # If date_range is provided, check if this date is in range
                    if date_range and not self._is_date_in_range(url_date, date_range[0], date_range[1]):
                        continue
                    
                    url = f"https://www.indiabix.com/current-affairs/{url_date}/"
                    
                    # Check if URL has already been processed
                    if not force_process and url in processed_urls:
                        logger.info(f"Skipping already processed URL: {url}")
                        skipped_urls.append(url)
                    else:
                        urls_to_process.append(url)
            
            if not urls_to_process:
                if skipped_urls:
                    logger.info(f"All URLs have already been processed. Skipped {len(skipped_urls)} URLs.")
                else:
                    logger.info("No URLs to process")
                
                if specific_date:
                    logger.warning(f"No new URLs found for date: {specific_date}")
                return []
                
            logger.info(f"Generated {len(urls_to_process)} URLs to process. Skipped {len(skipped_urls)} already processed URLs.")
            
            # Process URLs asynchronously
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                tasks = [self.process_url(url, session, processed_urls, force_process) for url in urls_to_process]
                results = await asyncio.gather(*tasks)
                
                # Flatten the list of lists
                for questions in results:
                    if questions:  # Only add to all_questions if there are actually questions
                        all_questions.extend(questions)
            
            logger.info(f"Processed {len(all_questions)} questions from {len(urls_to_process)} URLs")
                
            return all_questions
            
        except Exception as e:
            logger.error(f"Error in fetch_all_questions: {e}")
            return []
            
    async def fetch_questions_from_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Fetch questions from a specific URL
        
        Args:
            url: The URL to fetch questions from
            
        Returns:
            List of extracted questions
        """
        try:
            logger.info(f"Fetching questions from URL: {url}")
            return await self.process_specific_url(url, force_process=True)
        except Exception as e:
            logger.error(f"Error fetching questions from URL {url}: {e}")
            return [] 