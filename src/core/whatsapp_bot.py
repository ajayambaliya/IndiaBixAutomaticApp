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
                process = await asyncio.create_subprocess_exec(
                    "node", str(self.index_js), str(abs_pdf_path), caption,
                    cwd=str(self.node_script_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Stream stdout in real-time
                async def stream_output(stream, is_stderr=False):
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        
                        line_text = line.decode('utf-8', errors='replace').strip()
                        if not line_text: continue

                        if is_stderr:
                            logger.error(f"WhatsApp Bot Error: {line_text}")
                        else:
                            # If it looks like a QR code part, print it raw to keep formatting
                            if any(c in line_text for c in "▄█▀"):
                                print(line_text)
                            elif "QR RECEIVED" in line_text:
                                print("\n" + "="*50)
                                print("!!! WHATSAPP QR CODE DETECTED !!!")
                                print("="*50 + "\n")
                                logger.info(line_text)
                            else:
                                logger.info(f"WhatsApp Bot: {line_text}")

                # Run stdout and stderr streaming concurrently
                await asyncio.gather(
                    stream_output(process.stdout),
                    stream_output(process.stderr, is_stderr=True)
                )

                await process.wait()
                
                if process.returncode == 0:
                    logger.info(f"Successfully finished WhatsApp broadcast for {abs_pdf_path}")
                else:
                    logger.error(f"WhatsApp Bot process exited with code {process.returncode}")
                    
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
