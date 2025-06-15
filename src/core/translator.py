"""
Translator module using Mistral AI API for translations.
"""
import asyncio
import logging
import time
import os # Added for environment variable access
import re
from typing import List, Dict, Any, Optional, Union

# Update imports for Mistral AI client using the correct API for version 0.4.2
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# Configure logging
logger = logging.getLogger(__name__)

# Mistral API Configuration
# Load API key from environment variable, with a fallback to the hardcoded one
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_MODEL = "mistral-small-latest"  # Using a recommended small model for speed and cost
REQUEST_DELAY_SECONDS = 3  # Increased from 1 to 3 seconds for better results

# Global variable to track the last API call time
last_api_call_time = 0

def is_primarily_gujarati(text: str) -> bool:
    """
    Check if the given text is primarily in Gujarati script.
    
    Args:
        text: Text to check
        
    Returns:
        True if the text is primarily Gujarati, False otherwise
    """
    if not text:
        return False
        
    # Gujarati Unicode range: U+0A80 to U+0AFF
    gujarati_pattern = re.compile(r'[\u0A80-\u0AFF]')
    
    # Count Gujarati characters
    gujarati_chars = len(gujarati_pattern.findall(text))
    
    # If at least 30% of characters are Gujarati, consider it primarily Gujarati
    # This threshold can be adjusted based on needs
    return gujarati_chars > len(text) * 0.3

def should_skip_translation(text: str) -> bool:
    """
    Check if the text should be skipped for translation (e.g., numbers, percentages, ordinals).
    
    Args:
        text: Text to check
        
    Returns:
        True if the text should be skipped, False otherwise
    """
    if not text or not text.strip():
        return True
    
    # Skip single digits or comma-separated digits (e.g., "1, 2, 3, 4")
    if re.match(r'^[\d\s,]+$', text.strip()):
        return True
    
    # Skip percentages (e.g., "1%, 5%, 10%")
    if re.match(r'^[\d\s,.%]+$', text.strip()):
        return True
    
    # Skip ordinals (e.g., "1st, 2nd, 3rd")
    if re.match(r'^[\d\s,]+(st|nd|rd|th)([,\s]+([\d]+)(st|nd|rd|th))*$', text.strip()):
        return True
    
    # Skip date formats
    if re.match(r'^[\d]{1,2}[-/.][\d]{1,2}[-/.][\d]{2,4}$', text.strip()):
        return True
    
    # Skip time formats
    if re.match(r'^[\d]{1,2}:[\d]{1,2}(:\d{1,2})?(\s*(AM|PM|am|pm))?$', text.strip()):
        return True
    
    return False

async def translate_with_mistral_api(text_to_translate: str, target_lang: str = "gu", source_lang: str = "en") -> Optional[str]:
    """
    Translate text using the Mistral AI API.

    Args:
        text_to_translate: The text to translate.
        target_lang: The target language code (e.g., "gu" for Gujarati).
        source_lang: The source language code (e.g., "en" for English).

    Returns:
        The translated text, or None if translation fails.
    """
    global last_api_call_time
    if not text_to_translate or not text_to_translate.strip():
        return text_to_translate
        
    # Skip translation if the text should be skipped
    if should_skip_translation(text_to_translate):
        logger.info(f"Skipping translation for numeric/special content: '{text_to_translate}'")
        return text_to_translate
        
    # Skip translation if the text is already primarily in Gujarati
    if target_lang == "gu" and is_primarily_gujarati(text_to_translate):
        logger.info(f"Text is already primarily in Gujarati, skipping translation: '{text_to_translate[:30]}...'")
        return text_to_translate
        
    # Check if API key is available
    if not MISTRAL_API_KEY:
        logger.error("Mistral API key not found. Set the MISTRAL_API_KEY environment variable.")
        return text_to_translate  # Return original text if no API key

    # Ensure a delay between API calls
    current_time = time.monotonic()
    time_since_last_call = current_time - last_api_call_time
    if time_since_last_call < REQUEST_DELAY_SECONDS:
        await asyncio.sleep(REQUEST_DELAY_SECONDS - time_since_last_call)
    
    last_api_call_time = time.monotonic()

    # Maximum number of retry attempts
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            client = MistralClient(api_key=MISTRAL_API_KEY)

            # Improved prompt for better Gujarati translation without English text
            prompt = f"""Translate the following English text to Gujarati.
IMPORTANT INSTRUCTIONS:
1. Return ONLY the Gujarati translation, with no English text, explanations, or notes
2. Ensure the Gujarati translation is natural, grammatically correct, and preserves the original meaning
3. Use proper Gujarati script and grammar
4. Do not transliterate English words unless absolutely necessary
5. Do not include the original English text in your response
6. Do not include phrases like "Gujarati translation:" in your response
7. Do not wrap your response in quotes

English text: "{text_to_translate}"
"""
            
            messages = [
                ChatMessage(role="user", content=prompt)
            ]

            logger.info(f"Sending translation request to Mistral API for text: '{text_to_translate[:50]}...' (Attempt {retry_count + 1})")
            
            # Make the API call (using async client if available, or running sync in executor)
            loop = asyncio.get_event_loop()
            chat_response = await loop.run_in_executor(
                None,  # Uses the default ThreadPoolExecutor
                lambda: client.chat(model=MISTRAL_MODEL, messages=messages)
            )

            if chat_response and hasattr(chat_response, 'choices') and chat_response.choices:
                translated_text = chat_response.choices[0].message.content.strip()
                
                # Clean up the response
                # Remove any phrases like "Gujarati translation:" or "Here's the Gujarati translation:"
                cleanup_phrases = [
                    "gujarati translation:", 
                    "here's the gujarati translation:", 
                    "here is the gujarati translation:",
                    "translation:",
                    "in gujarati:",
                    "translated text:"
                ]
                
                for phrase in cleanup_phrases:
                    if translated_text.lower().startswith(phrase):
                        translated_text = translated_text[len(phrase):].strip()
                
                # Remove quotes if they wrap the entire text
                if (translated_text.startswith('"') and translated_text.endswith('"')) or \
                   (translated_text.startswith("'") and translated_text.endswith("'")):
                    translated_text = translated_text[1:-1].strip()
                
                # Further cleaning if the model includes the original English text
                if text_to_translate.lower() in translated_text.lower():
                    # This is a simple heuristic, might need refinement
                    translated_text = translated_text.lower().replace(text_to_translate.lower(), "").strip()

                # Check if translation was successful (contains Gujarati characters)
                if target_lang == "gu" and not is_primarily_gujarati(translated_text):
                    logger.warning(f"Translation doesn't appear to be in Gujarati: '{translated_text[:50]}...' (Attempt {retry_count + 1})")
                    
                    # If we've reached the maximum retries, use a different approach for the last attempt
                    if retry_count == max_retries - 1:
                        logger.warning("Final attempt with alternative prompt structure")
                        retry_prompt = f"""Translate to Gujarati: {text_to_translate}
                        
Only respond with the Gujarati translation in Gujarati script. No English text, no explanations."""
                    else:
                        # Try with a more explicit prompt for intermediate retries
                        retry_prompt = f"""Translate this English text to Gujarati language using Gujarati script (not Latin/English letters).
ONLY output the Gujarati translation in Gujarati script, nothing else.

English text: "{text_to_translate}"
"""
                    
                    # Increment retry count and continue to next attempt
                    retry_count += 1
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                    last_api_call_time = time.monotonic()
                    messages = [ChatMessage(role="user", content=retry_prompt)]
                    continue
                
                logger.info(f"Successfully translated to Gujarati: '{translated_text[:50]}...' (Attempt {retry_count + 1})")
                return translated_text
            else:
                logger.error(f"Mistral API did not return a valid translation (Attempt {retry_count + 1}).")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(REQUEST_DELAY_SECONDS * 2)  # Longer delay before retry
                    last_api_call_time = time.monotonic()
                    continue
                return text_to_translate  # Return original text after all retries failed
        except Exception as e:
            logger.error(f"Error during Mistral API translation (Attempt {retry_count + 1}): {e}")
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(REQUEST_DELAY_SECONDS * 2)  # Longer delay before retry
                last_api_call_time = time.monotonic()
                continue
            return text_to_translate  # Return original text on error after all retries
    
    # If we've exhausted all retries
    return text_to_translate

async def translate_content(
    data: Union[List[Dict[str, Any]], Dict[str, Any]], 
    target_lang: str = "gu",
    source_lang: str = "en"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Translate all relevant text fields in question data
    from source language to target language using Mistral AI.

    Args:
        data: List of question objects or a dictionary containing question data.
        target_lang: Target language code.
        source_lang: Source language code.

    Returns:
        Translated data in the same format as the input.
    """
    if target_lang == source_lang:
        return data

    # If input is a dictionary, handle it differently
    if isinstance(data, dict):
        logger.info(f"Translating dictionary data from {source_lang} to {target_lang} using Mistral AI.")
        translated_data = data.copy()  # Create a shallow copy
        
        # Translate categorized questions if they exist
        if 'categorized_questions' in translated_data and isinstance(translated_data['categorized_questions'], dict):
            for category, questions in translated_data['categorized_questions'].items():
                if isinstance(questions, list):
                    # Translate each question in the category
                    for i, question in enumerate(questions):
                        # Translate question text
                        if 'question_text' in question and isinstance(question['question_text'], str):
                            question['question_text'] = await translate_with_mistral_api(
                                question['question_text'], target_lang, source_lang
                            ) or question['question_text']
                        
                        # Translate options if they exist as a dictionary
                        if 'options' in question and isinstance(question['options'], dict):
                            for option_key, option_text in question['options'].items():
                                if isinstance(option_text, str) and not should_skip_translation(option_text):
                                    question['options'][option_key] = await translate_with_mistral_api(
                                        option_text, target_lang, source_lang
                                    ) or option_text
                        
                        # Translate explanation if it exists
                        if 'explanation' in question and isinstance(question['explanation'], str):
                            question['explanation'] = await translate_with_mistral_api(
                                question['explanation'], target_lang, source_lang
                            ) or question['explanation']
        
        # Translate title if it exists
        if 'title' in translated_data and isinstance(translated_data['title'], str):
            translated_data['title'] = await translate_with_mistral_api(translated_data['title'], target_lang, source_lang) or translated_data['title']
        
        # Translate any other string fields that might need translation
        for key, value in translated_data.items():
            if isinstance(value, str) and key not in ['language', 'date', 'generation_date', 'source'] and not should_skip_translation(value):
                translated_data[key] = await translate_with_mistral_api(value, target_lang, source_lang) or value
        
        return translated_data
    
    # Original list-based translation logic
    questions_data = data
    translated_questions_data = []
    total_questions = len(questions_data)
    logger.info(f"Starting translation of {total_questions} questions from {source_lang} to {target_lang} using Mistral AI.")

    for i, item in enumerate(questions_data):
        logger.info(f"Translating question {i+1}/{total_questions}...")
        translated_item = item.copy()  # Create a shallow copy

        # Text fields to translate
        text_fields = ['question', 'question_text', 'correct_answer', 'explanation']
        
        # Translate main text fields
        for field in text_fields:
            if field in translated_item and isinstance(translated_item[field], str) and not should_skip_translation(translated_item[field]):
                original_text = translated_item[field]
                translated_text = await translate_with_mistral_api(original_text, target_lang, source_lang)
                if translated_text:
                    translated_item[field] = translated_text
                else:
                    logger.warning(f"Translation failed for field '{field}' in question {i+1}. Keeping original.")
        
        # Translate options if they exist
        if 'options' in translated_item:
            if isinstance(translated_item['options'], dict):
                # Handle options as a dictionary
                translated_options = translated_item['options'].copy()
                for option_key, option_text in translated_options.items():
                    if isinstance(option_text, str) and not should_skip_translation(option_text):
                        translated_option_text = await translate_with_mistral_api(option_text, target_lang, source_lang)
                        if translated_option_text:
                            translated_options[option_key] = translated_option_text
                translated_item['options'] = translated_options
            elif isinstance(translated_item['options'], list):
                # Handle options as a list
                translated_options = []
                for option_text in translated_item['options']:
                    if isinstance(option_text, str) and not should_skip_translation(option_text):
                        translated_option_text = await translate_with_mistral_api(option_text, target_lang, source_lang)
                        translated_options.append(translated_option_text if translated_option_text else option_text)
                    else:
                        translated_options.append(option_text)
                translated_item['options'] = translated_options

        translated_questions_data.append(translated_item)
        logger.info(f"Finished translating question {i+1}/{total_questions}.")

    logger.info(f"Successfully translated {len(translated_questions_data)} questions to {target_lang}.")
    return translated_questions_data

# Example usage (can be removed or commented out for production)
async def _test_translation():
    sample_question = {
        "question_text": "What is the capital of France?",
        "options": {
            "option_a": "Berlin",
            "option_b": "Paris",
            "option_c": "London",
            "option_d": "Madrid"
        },
        "correct_answer": "Paris",
        "explanation": "Paris is the capital and most populous city of France."
    }
    translated_data = await translate_content([sample_question], "gu", "en")
    if translated_data:
        print("Translated Data:")
        import json
        print(json.dumps(translated_data, indent=2, ensure_ascii=False))

def _test_skip_translation():
    """Test the should_skip_translation function with various inputs"""
    test_cases = [
        ("1, 2, 3, 4", True),
        ("1%, 5%, 10%", True),
        ("1st, 2nd, 3rd", True),
        ("10/12/2023", True),
        ("15:30", True),
        ("3:45 PM", True),
        ("Option A", False),
        ("This is regular text", False),
        ("Text with 123 numbers", False),
        ("", True),
        ("   ", True)
    ]
    
    print("Testing skip translation detection:")
    for text, expected in test_cases:
        result = should_skip_translation(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text}' -> {result} (expected: {expected})")

if __name__ == '__main__':
    # Configure basic logging for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Test skip translation function
    _test_skip_translation()
    
    # To run the translation test, you would typically do:
    # asyncio.run(_test_translation())
    # However, ensure MISTRAL_API_KEY is set correctly.
    
    print("Translator module with Mistral AI loaded. Run test function for a demo.")