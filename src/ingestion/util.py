"""
Utility module for Azure AI Accelerator application.

This module provides helper functions for:
- Environment configuration
"""

from io import StringIO
from subprocess import run, PIPE
import logging
from dotenv import load_dotenv

def load_dotenv_from_azd():
    """
    Loads environment variables from Azure Developer CLI (azd) or .env file.

    Attempts to load environment variables using the azd CLI first.
    If that fails, falls back to loading from a .env file in the current directory.
    """
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info(f"Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info(f"AZD environment not found. Trying to load from .env file...")
        load_dotenv()