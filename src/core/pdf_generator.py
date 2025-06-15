"""
PDF Generator module for creating modern PDFs
"""
import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import jinja2
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('pdf_generator.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

class ModernPDFGenerator:
    """Modern PDF Generator class using Playwright"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize PDF Generator with configuration"""
        self.config = config
        self.template_dir = Path(config['template_dir'])
        self.output_dir = Path(config['output_dir'])
        self.static_dir = Path(config['static_dir'])
        self.pdf_config = config['pdf_config']
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.jinja_env.filters['date_format'] = self._date_format_filter
    
    def _date_format_filter(self, value, format_string="%d-%m-%Y"):
        """Format date strings in templates"""
        if not value:
            return ""
        
        try:
            from datetime import datetime
            date_obj = datetime.strptime(value, "%Y-%m-%d")
            return date_obj.strftime(format_string)
        except Exception as e:
            logger.error(f"Error formatting date: {e}")
            return value
    
    async def generate_pdf(self, template_name: str, data: Dict[str, Any], output_filename: str) -> str:
        """Generate PDF from data using Playwright
        
        Args:
            template_name: Name of the template to use
            data: Data to pass to the template
            output_filename: Name of the output PDF file
            
        Returns:
            Path to the generated PDF file
        """
        try:
            # Ensure data has required fields with defaults
            if 'stats' not in data:
                logger.warning("Stats not found in data, adding default stats")
                data['stats'] = {
                    'total': len(data.get('categorized_questions', {}).get('general', [])),
                    'difficulty': {'easy': 0, 'medium': 0, 'hard': 0},
                    'categories': {'general': len(data.get('categorized_questions', {}).get('general', []))}
                }
            
            # Create a context dictionary with all the data
            context = {
                'static_dir': str(self.static_dir),
                'config': self.config,  # Add config to context
            }
            
            # Add all data to context, but avoid overwriting config if it exists
            if isinstance(data, dict):
                for key, value in data.items():
                    if key != 'config':  # Avoid duplicate config
                        context[key] = value
            else:
                # Handle case where data is not a dictionary
                logger.warning(f"Data is not a dictionary, it's a {type(data)}. Converting to context['data']")
                context['data'] = data
            
            # Render HTML template
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**context)
            
            # Create a temporary HTML file
            temp_html_path = self.output_dir / f"{output_filename}.html"
            with open(temp_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Convert HTML to PDF using Playwright
            output_path = self.output_dir / output_filename
            
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                # Load the HTML file
                await page.goto(f"file://{temp_html_path.absolute()}")
                
                # Wait for any JavaScript to execute and images to load
                await page.wait_for_load_state("networkidle")
                
                # Generate PDF
                await page.pdf(
                    path=str(output_path),
                    format=self.pdf_config.get("format", "A4"),
                    margin={
                        "top": self.pdf_config.get("margin", {}).get("top", "0.5in"),
                        "right": self.pdf_config.get("margin", {}).get("right", "0.5in"),
                        "bottom": self.pdf_config.get("margin", {}).get("bottom", "0.5in"),
                        "left": self.pdf_config.get("margin", {}).get("left", "0.5in")
                    },
                    print_background=self.pdf_config.get("printBackground", True),
                    display_header_footer=False
                )
                
                await browser.close()
            
            # Clean up temporary HTML file
            if os.path.exists(temp_html_path):
                os.remove(temp_html_path)
            
            logger.info(f"PDF generated successfully: {output_path}")
            return str(output_path)
        
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise
    
    def _get_footer_template(self) -> str:
        """Get footer template for PDF"""
        try:
            footer_template = self.jinja_env.get_template(self.config['templates']['footer'])
            return footer_template.render(config=self.config)
        except Exception as e:
            logger.error(f"Error loading footer template: {e}")
            return "<div style='text-align: center; width: 100%; font-size: 10px;'>Page <span class='pageNumber'></span> of <span class='totalPages'></span></div>" 