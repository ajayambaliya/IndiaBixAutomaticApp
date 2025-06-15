"""
Template Manager for handling HTML templates and data preparation
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core.translator import translate_content as mistral_translate_questions_list
from src.core.translator import translate_with_mistral_api as mistral_translate_single_text

logger = logging.getLogger(__name__)

class TemplateManager:
    """Manage templates and prepare data for PDF generation"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the template manager with optional config path"""
        self.config = self._load_config(config_path)
        
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from JSON file or use defaults"""
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config from {config_path}: {e}")
        
        # Default configuration
        return {
            "templates": {
                "base": "base.html",
                "cover": "cover_page.html",
                "content": "content_page.html",
                "footer": "footer.html",
                "promotion": "promotion.html"
            },
            "branding": {
                "title": "Current Affairs Quiz",
                "logo": "logo.png",
                "channels": {
                    "english": "@daily_current_all_source",
                    "gujarati": "@currentadda"
                },
                "join_link": "https://t.me/+UkTcRyx3rhERLwQR"
            }
        }
    
    def prepare_pdf_data(self, questions: List[Dict[str, Any]], language: str = "en") -> Dict[str, Any]:
        """Prepare data for PDF generation"""
        if not questions:
            logger.warning("No questions provided for PDF generation")
            return {}
        
        # Get date from first question
        date = questions[0].get('date', 'Unknown Date')
        
        # Calculate statistics
        stats = self._calculate_statistics(questions)
        
        # Group questions by category
        categorized_questions = self._categorize_questions(questions)
        
        # Translate content if needed
        if language != "en":
            try:
                # Run the async translation logic
                categorized_questions = asyncio.run(self._translate_content_async(categorized_questions, language))
            except Exception as e:
                logger.error(f"Error during async translation in prepare_pdf_data: {e}. Using original content.")
                # Fallback to original categorized_questions if async translation fails
        
        # Prepare final data structure
        pdf_data = {
            "title": f"Current Affairs Quiz - {date} ({language.upper()})",
            "date": date,
            "language": language,
            "stats": stats,
            "categorized_questions": categorized_questions,
            "branding": self.config.get("branding", {}),
            "total_questions": len(questions)
        }
        
        return pdf_data
    
    def _calculate_statistics(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for the cover page"""
        # Count questions by difficulty
        difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}
        for question in questions:
            difficulty = question.get('difficulty', 'medium')
            difficulty_counts[difficulty] += 1
        
        # Count questions by category
        category_counts = {}
        for question in questions:
            category = question.get('category', 'general')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            "difficulty": difficulty_counts,
            "categories": category_counts,
            "total": len(questions)
        }
    
    def _categorize_questions(self, questions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group questions by category"""
        categorized = {}
        
        for question in questions:
            category = question.get('category', 'general')
            if category not in categorized:
                categorized[category] = []
            
            categorized[category].append(question)
        
        return categorized
    
    async def _translate_content_async(self, categorized_questions: Dict[str, List[Dict[str, Any]]], 
                                 target_language: str) -> Dict[str, List[Dict[str, Any]]]:
        """Asynchronously translate question content and categories to target language using Mistral AI."""
        if not categorized_questions:
            return {}

        all_questions_flat = []
        original_category_map = {} # To map original questions back to their categories
        question_id_counter = 0

        for category, questions_in_category in categorized_questions.items():
            for q_idx, question in enumerate(questions_in_category):
                # Add a temporary unique ID to each question to map it back after translation
                # This is important because translation might slightly alter text, making direct matching hard
                temp_id = f"temp_q_{category}_{question_id_counter}"
                question['_temp_id_'] = temp_id
                question_id_counter += 1
                all_questions_flat.append(question)
                original_category_map[temp_id] = (category, q_idx) # Store original category and index

        # Translate all questions in one batch
        logger.info(f"Starting batch translation of {len(all_questions_flat)} questions to {target_language} using Mistral.")
        translated_questions_flat = await mistral_translate_questions_list(
            all_questions_flat, 
            source_lang="en", 
            target_lang=target_language
        )
        logger.info(f"Finished batch translation of questions.")

        # Reconstruct categorized questions with translated content
        # And translate category names
        translated_categorized_questions: Dict[str, List[Dict[str, Any]]] = {}
        
        # Create a dictionary of translated questions by their temp_id for easy lookup
        translated_questions_dict_by_id = {q['_temp_id_']: q for q in translated_questions_flat if '_temp_id_' in q}

        processed_categories = set()

        for temp_id, (original_category_name, _) in original_category_map.items():
            translated_question = translated_questions_dict_by_id.get(temp_id)
            if not translated_question:
                logger.warning(f"Could not find translated question for temp_id: {temp_id}. Skipping.")
                # Attempt to find the original question to put it back untranslated
                original_q_found = None
                for q_orig_list in categorized_questions.values():
                    for q_orig in q_orig_list:
                        if q_orig.get('_temp_id_') == temp_id:
                            original_q_found = q_orig
                            break
                    if original_q_found:
                        break
                if original_q_found:
                    translated_question = original_q_found # Fallback to original
                else:
                    continue # Should not happen if map is correct

            # Clean up temporary ID
            if '_temp_id_' in translated_question:
                del translated_question['_temp_id_']
            
            translated_category_name = original_category_name
            if original_category_name not in processed_categories and original_category_name.lower() != "general": # Avoid translating "general" or re-translating
                logger.info(f"Translating category name: {original_category_name} to {target_language}")
                translated_cat_name_api_result = await mistral_translate_single_text(
                    original_category_name, 
                    target_lang=target_language, 
                    source_lang="en"
                )
                if translated_cat_name_api_result:
                    translated_category_name = translated_cat_name_api_result
                else:
                    logger.warning(f"Failed to translate category name: {original_category_name}. Using original.")
                processed_categories.add(original_category_name) # Mark as processed (attempted translation)
            
            if translated_category_name not in translated_categorized_questions:
                translated_categorized_questions[translated_category_name] = []
            
            # This ordering might not be perfectly preserved if questions within a category were identical
            # before translation and their distinctness relied on the _temp_id_.
            # However, for most practical purposes, appending should be fine.
            # If strict ordering is critical and questions can be identical, a more robust mapping is needed.
            translated_categorized_questions[translated_category_name].append(translated_question)

        # Ensure original untranslated questions are also put back if their category was not processed
        # or if some questions were missed. This is a fallback.
        for original_cat, original_qs_list in categorized_questions.items():
            found_in_translated = False
            for trans_cat_qs_list in translated_categorized_questions.values():
                if any(oq.get('question_text') == tq.get('question_text') for oq in original_qs_list for tq in trans_cat_qs_list): # Basic check
                    found_in_translated = True
                    break
            if not found_in_translated:
                 # If the whole category seems missing, add it back with original questions (remove temp_ids)
                logger.warning(f"Category '{original_cat}' seems to be missing after translation. Adding it back with original questions.")
                cleaned_original_qs_list = []
                for oq in original_qs_list:
                    oq_copy = oq.copy()
                    if '_temp_id_' in oq_copy: del oq_copy['_temp_id_']
                    cleaned_original_qs_list.append(oq_copy)
                translated_categorized_questions[original_cat] = cleaned_original_qs_list
        
        return translated_categorized_questions
    
    def get_template_paths(self) -> Dict[str, str]:
        """Get paths for all templates"""
        templates = self.config.get("templates", {})
        return {
            key: str(Path("templates") / path) 
            for key, path in templates.items()
        }
        
    def get_template(self, template_type: str) -> str:
        """
        Get the template name based on the template type
        
        Args:
            template_type: The type of template to get (e.g., 'modern', 'simple')
            
        Returns:
            The template name/path
        """
        templates = self.config.get("templates", {})
        
        # For now, we only have one template type, so return the base template
        if template_type == "modern":
            return templates.get("base", "base.html")
        elif template_type == "simple":
            return templates.get("simple", "simple.html")
        else:
            # Default to base template
            return templates.get("base", "base.html") 