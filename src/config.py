"""
Configuration module for the Virtual Try-On API
Contains logger setup and environment variables
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# -------------------------
# Logger Setup
# -------------------------
def setup_logger(name: str = __name__, log_file: str = "newfile.log") -> logging.Logger:
    """
    Set up and return a logger with both file and console handlers

    Args:
        name: Logger name (usually __name__)
        log_file: Path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Create the main application logger
logger = setup_logger("src")

# -------------------------
# Environment Variables
# -------------------------
GEMINI_KEY = os.getenv("GEMINI_KEY")
TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET")
APP_SECRET = os.getenv("APP_SECRET")  # Shared secret with Cloudflare Worker

# supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


# Log configuration status
logger.info("Configuration loaded successfully")
logger.debug(f"GEMINI_KEY configured: {bool(GEMINI_KEY)}")
logger.debug(f"TURNSTILE_SECRET configured: {bool(TURNSTILE_SECRET)}")
logger.debug(f"APP_SECRET configured: {bool(APP_SECRET)}")
logger.debug(f"SUPABASE_URL configured: {bool(SUPABASE_URL)}")
logger.debug(f"SUPABASE_KEY configured: {bool(SUPABASE_KEY)}")
logger.debug(f"SUPABASE_SERVICE_KEY configured: {bool(SUPABASE_SERVICE_KEY)}")
