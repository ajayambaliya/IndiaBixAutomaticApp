"""
Translator module using Google Gemini 3.1 Flash API (google-genai SDK) for translations.
"""
import asyncio
import logging
import time
import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from google import genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Configure logging
logger = logging.getLogger(__name__)

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-flash-latest"  # Use latest flash
REQUEST_DELAY_SECONDS = 4.5  # To stay safely under 15 RPM
DAILY_REQUEST_LIMIT = 40     # User-specified safety limit
USAGE_FILE = ".gemini_usage.json"
CACHE_FILE = ".translation_cache.json"

class UsageTracker:
    """Tracks Gemini API usage to enforce daily limits."""
    def __init__(self, limit: int = DAILY_REQUEST_LIMIT):
        self.limit = limit
        self.usage_file = USAGE_FILE
        self._load_usage()

    def _load_usage(self):
        self.today = datetime.now().strftime("%Y-%m-%d")
        if os.path.exists(self.usage_file):
            try:
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                    self.count = data.get("count", 0) if data.get("date") == self.today else 0
            except: self.count = 0
        else: self.count = 0

    def _save_usage(self):
        try:
            with open(self.usage_file, 'w') as f:
                json.dump({"date": self.today, "count": self.count}, f)
        except: pass

    def increment(self):
        self.count += 1
        self._save_usage()

    def can_make_request(self) -> bool:
        return self.count < self.limit

class TranslationCache:
    """Persistent cache for translations to avoid redundant API calls."""
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except: pass

    def get(self, text: str, lang: str) -> Optional[str]:
        return self.cache.get(f"{lang}:{text}")

    def set(self, text: str, translated: str, lang: str):
        self.cache[f"{lang}:{text}"] = translated
        self._save_cache()

# Global instances
usage_tracker = UsageTracker()
translation_cache = TranslationCache()

def is_primarily_gujarati(text: str) -> bool:
    """Check if the given text is primarily in Gujarati script."""
    if not text:
        return False
    gujarati_pattern = re.compile(r'[\u0A80-\u0AFF]')
    gujarati_chars = len(gujarati_pattern.findall(text))
    return gujarati_chars > len(text) * 0.3

def should_skip_translation(text: str) -> bool:
    """Check if the text should be skipped for translation."""
    if not text or not text.strip():
        return True
    if re.match(r'^[\d\s,]+$', text.strip()): return True
    if re.match(r'^[\d\s,.%]+$', text.strip()): return True
    if re.match(r'^[\d\s,]+(st|nd|rd|th)([,\s]+([\d]+)(st|nd|rd|th))*$', text.strip()): return True
    if re.match(r'^[\d]{1,2}[-/.][\d]{1,2}[-/.][\d]{2,4}$', text.strip()): return True
    if re.match(r'^[\d]{1,2}:[\d]{1,2}(:\d{1,2})?(\s*(AM|PM|am|pm))?$', text.strip()): return True
    return False

class GeminiTranslator:
    """Handles interaction with Google Gemini API using google-genai SDK."""
    
    def __init__(self, api_key: str):
        if not api_key:
            logger.error("GEMINI_API_KEY not found.")
            self.client = None
            return
            
        self.client = genai.Client(api_key=api_key)
        self.last_call_time = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=10),
        retry=retry_if_exception_type((Exception)),
        reraise=True
    )
    async def _call_gemini(self, prompt: str) -> str:
        """Internal call to Gemini with RPM protection and retry logic."""
        if not self.client:
            raise ValueError("Gemini client not initialized.")

        # RPM Throttling
        elapsed = time.monotonic() - self.last_call_time
        if elapsed < REQUEST_DELAY_SECONDS:
            await asyncio.sleep(REQUEST_DELAY_SECONDS - elapsed)

        if not usage_tracker.can_make_request():
            logger.error(f"Daily Gemini request limit reached ({DAILY_REQUEST_LIMIT}/day).")
            raise QuotaExceededError("Daily limit reached.")

        logger.info(f"Sending request to Gemini (Daily Count: {usage_tracker.count + 1})")
        
        # google-genai supports both sync and async. We'll use sync in executor for simplicity with existing code
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    'system_instruction': 'You are a professional English to Gujarati translator. Output valid JSON only.',
                    'response_mime_type': 'application/json'
                }
            )
        )
        
        self.last_call_time = time.monotonic()
        usage_tracker.increment()
        
        if not response or not response.text:
            raise ValueError("Gemini returned empty response.")
            
        return response.text

    def _sanitize_json(self, text: str) -> str:
        """Strips markdown fences and attempts to fix common LLM JSON errors."""
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text.strip()

    async def translate_batch(self, content_dict: Dict[str, str], target_lang: str = "gu") -> Dict[str, str]:
        """Translates a dictionary of strings in one batch with caching."""
        if not content_dict:
            return {}

        result = {}
        to_translate = {}
        
        # 1. Check cache first
        for key, text in content_dict.items():
            cached = translation_cache.get(text, target_lang)
            if cached:
                result[key] = cached
            else:
                to_translate[key] = text
        
        if not to_translate:
            return result

        # 2. Translate only what's not in cache
        prompt = f"Translate the following English strings into Gujarati script. Preserve JSON keys.\n\n{json.dumps(to_translate, ensure_ascii=False)}"
        
        try:
            raw_response = await self._call_gemini(prompt)
            sanitized = self._sanitize_json(raw_response)
            translated_dict = json.loads(sanitized)
            
            # Map results back and update cache
            for key, original_val in to_translate.items():
                translated_val = translated_dict.get(key, original_val)
                result[key] = translated_val
                # Cache it
                translation_cache.set(original_val, translated_val, target_lang)
                
            return result
            
        except Exception as e:
            logger.error(f"Batch translation failed: {e}")
            # Fill remaining results with original values if failed
            for key, val in to_translate.items():
                result[key] = val
            return result

class QuotaExceededError(Exception):
    pass

_translator: Optional[GeminiTranslator] = None

def get_translator():
    global _translator
    if _translator is None:
        _translator = GeminiTranslator(GEMINI_API_KEY)
    return _translator

async def translate_with_gemini_api(text: str, target_lang: str = "gu") -> str:
    """Wrapper for single string translation."""
    if should_skip_translation(text) or is_primarily_gujarati(text):
        return text
    translator = get_translator()
    result = await translator.translate_batch({"text": text}, target_lang)
    return result.get("text", text)

async def translate_content(
    data: Union[List[Dict[str, Any]], Dict[str, Any]], 
    target_lang: str = "gu",
    source_lang: str = "en"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Smart-Batching: Packs Title + All Questions into 1 request (max 30k chars) to minimize quota usage."""
    if target_lang == source_lang or not GEMINI_API_KEY:
        return data

    translator = get_translator()
    MAX_CHARS_PER_REQ = 30000  # Conservative safety limit for JSON processing
    
    if isinstance(data, dict):
        # 1. Flatten all questions
        all_questions = []
        if 'categorized_questions' in data:
            for category in data['categorized_questions']:
                for q in data['categorized_questions'][category]:
                    all_questions.append(q)
        
        if not all_questions and 'title' in data:
            data['title'] = await translate_with_gemini_api(data['title'], target_lang)
            return data

        # 2. Greedy Packing based on character count
        current_batch_payload = {}
        batch_q_indices = [] # To map back
        title_included = False
        
        # Start building the first (and likely only) batch
        if 'title' in data and not should_skip_translation(data['title']):
            current_batch_payload["_meta_title"] = data['title']
            title_included = True

        for q_idx, q in enumerate(all_questions):
            temp_payload = {}
            q_text = q.get('question_text', '')
            q_expl = q.get('explanation', '')
            
            if q_text and not should_skip_translation(q_text):
                temp_payload[f"q_{q_idx}_text"] = q_text
            if q_expl and not should_skip_translation(q_expl):
                temp_payload[f"q_{q_idx}_expl"] = q_expl
            if 'options' in q:
                for opt_key, opt_val in q['options'].items():
                    if opt_val and not should_skip_translation(opt_val):
                        temp_payload[f"q_{q_idx}_opt_{opt_key}"] = opt_val
            
            # Check if adding this question exceeds the char limit
            # (Simplistic check: current length + new payload length)
            current_size = len(json.dumps(current_batch_payload))
            new_item_size = len(json.dumps(temp_payload))
            
            if current_size + new_item_size > MAX_CHARS_PER_REQ and current_batch_payload:
                # Send current batch and start a new one
                translated = await translator.translate_batch(current_batch_payload, target_lang)
                _apply_translations(data, all_questions, translated)
                
                # Reset for next batch
                current_batch_payload = temp_payload
            else:
                # Add to current batch
                current_batch_payload.update(temp_payload)
        
        # Send the final (or only) batch
        if current_batch_payload:
            translated = await translator.translate_batch(current_batch_payload, target_lang)
            _apply_translations(data, all_questions, translated)

    return data

def _apply_translations(data: Dict[str, Any], questions: List[Dict[str, Any]], translated: Dict[str, str]):
    """Helper to map translated dictionary back to the objects."""
    if "_meta_title" in translated:
        data['title'] = translated["_meta_title"]
        
    for q_idx, q in enumerate(questions):
        if f"q_{q_idx}_text" in translated:
            q['question_text'] = translated[f"q_{q_idx}_text"]
        
        if f"q_{q_idx}_expl" in translated:
            q['explanation'] = translated[f"q_{q_idx}_expl"]
            
        if 'options' in q:
            for opt_key in q['options']:
                if f"q_{q_idx}_opt_{opt_key}" in translated:
                    q['options'][opt_key] = translated[f"q_{q_idx}_opt_{opt_key}"]