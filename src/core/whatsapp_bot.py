"""
WhatsApp Bot Wrapper for calling the Node.js whatsapp-web.js implementation
Created by Ajay Ambaliya for Current Adda
"""
import os
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('whatsapp_bot.log'), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

class WhatsAppBot:
    """Wrapper class for the Node.js WhatsApp bot"""
    
    def __init__(self, node_script_dir: str = "whatsapp"):
        """Initialize with the directory containing index.js"""
        self.node_script_dir = Path(node_script_dir).absolute()
        self.index_js = self.node_script_dir / "index.js"
        
    async def send_pdfs(self, pdf_paths: List[str], caption: str = ""):
        """Call the Node.js script to send PDFs"""
        if not self.index_js.exists():
            logger.error(f"Node.js script not found at {self.index_js}")
            return False
            
        for pdf_path in pdf_paths:
            abs_pdf_path = Path(pdf_path).absolute()
            if not abs_pdf_path.exists():
                logger.error(f"PDF file not found: {abs_pdf_path}")
                continue
                
            logger.info(f"Triggering Node.js WhatsApp bot for: {abs_pdf_path}")
            
            try:
                # Run the node script
                # command: node index.js <pdf_path> <caption chunks...>
                process = await asyncio.create_subprocess_exec(
                    "node", str(self.index_js), str(abs_pdf_path), caption,
                    cwd=str(self.node_script_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Wait for the process to complete and capture output
                stdout, stderr = await process.communicate()
                
                # Helper to safely decode and clean output for Windows console
                def safe_log(data: bytes):
                    if not data: return ""
                    try:
                        # Try to decode normally first
                        return data.decode('utf-8')
                    except UnicodeDecodeError:
                        # Fallback to ignore errors if it's really messy
                        return data.decode('utf-8', errors='replace')

                if stdout:
                    output = safe_log(stdout)
                    # If it looks like a QR code, print it directly to console for the user to scan
                    if "QR RECEIVED" in output or "▄▄▄▄▄" in output:
                        print("\n" + "="*50)
                        print("WHATSAPP QR CODE DETECTED - PLEASE SCAN")
                        print("="*50 + "\n")
                        print(output)
                        print("\n" + "="*50 + "\n")
                    else:
                        logger.info(f"Node.js Output:\n{output}")
                if stderr:
                    logger.error(f"Node.js Error:\n{safe_log(stderr)}")
                    
                if process.returncode == 0:
                    logger.info(f"Successfully triggered WhatsApp send for {abs_pdf_path}")
                else:
                    logger.error(f"Node.js process failed with return code {process.returncode}")
                    
            except Exception as e:
                logger.error(f"Exception during Node.js execution: {e}")
                
        return True

async def send_pdfs_to_whatsapp(groups: List[str], pdf_paths: List[str], caption: str = ""):
    """
    Helper function to send multiple PDFs to multiple groups.
    Note: The group names are handled inside the Node.js script via .env
    """
    bot = WhatsAppBot()
    await bot.send_pdfs(pdf_paths, caption)

if __name__ == "__main__":
    # Test
    # asyncio.run(send_pdfs_to_whatsapp([], ["test.pdf"], "Test Caption"))
    pass
