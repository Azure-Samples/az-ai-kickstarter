"""
Streamlit frontend application for AI blog post generation.

This script provides a web interface using Streamlit that communicates with a backend service
to generate blog posts on specified topics.
"""
import base64
import json
import logging
import os
import requests
import streamlit as st
from dotenv import load_dotenv
from io import StringIO
from subprocess import run, PIPE

def load_dotenv_from_azd():
    """
    Load environment variables from Azure Developer CLI (azd) or fallback to .env file.
    
    Attempts to retrieve environment variables using the 'azd env get-values' command.
    If unsuccessful, falls back to loading from a .env file.
    """
    result = run("azd env get-values", stdout=PIPE, stderr=PIPE, shell=True, text=True)
    if result.returncode == 0:
        logging.info(f"Found AZD environment. Loading...")
        load_dotenv(stream=StringIO(result.stdout))
    else:
        logging.info(f"AZD environment not found. Trying to load from .env file...")
        load_dotenv()

def get_principal_id():
    """
    Retrieve the current user's principal ID from request headers.
    If the application is running in Azure Container Apps, and is configured for authentication, 
    the principal ID is extracted from the 'x-ms-client-principal-id' header.
    If the header is not present, a default user ID is returned.
    
    Returns:
        str: The user's principal ID if available, otherwise 'default_user_id'
    """
    result = st.context.headers.get('x-ms-client-principal-id')
    logging.info(f"Retrieved principal ID: {result if result else 'default_user_id'}")
    return result if result else "default_user_id"

def get_principal_display_name():
    """
    Get the display name of the current user from the request headers.
    
    Extracts user information from the 'x-ms-client-principal' header used in 
    Azure Container Apps authentication.
    
    Returns:
        str: The user's display name if available, otherwise 'Default User'
        
    See https://learn.microsoft.com/en-us/azure/container-apps/authentication#access-user-claims-in-application-code for more information.
    """
    default_user_name = "Default User"
    principal = st.context.headers.get('x-ms-client-principal')
    if principal:
        principal = json.loads(base64.b64decode(principal).decode('utf-8'))
        claims = principal.get("claims", [])
        return next((claim["val"] for claim in claims if claim["typ"] == "name"), default_user_name)
    else:
        return default_user_name

def is_valid_json(json_string): 
    """
    Validate if a string is properly formatted JSON.
    
    Args:
        json_string (str): The string to validate as JSON
        
    Returns:
        bool: True if string is valid JSON, False otherwise
    """
    try: 
        json.loads(json_string) 
        return True 
    except json.JSONDecodeError: 
        return False

# Initialize environment
load_dotenv_from_azd()

# Setup sidebar with user information and logout link
st.sidebar.write(f"Welcome, {get_principal_display_name()}!")
st.sidebar.markdown(
    '<a href="/.auth/logout" target = "_self">Sign Out</a>', unsafe_allow_html=True
)

# Main content area - blog post generation
st.write("Requesting a blog post about cookies:")
result = None
with st.status("Agents are crafting a response...", expanded=True) as status:
    try:
        # Call backend API to generate blog post
        url = f'{os.getenv("BACKEND_ENDPOINT", "http://localhost:8000")}/blog'
        payload = {"topic": "cookies", "user_id": get_principal_id()}
        headers = {}
        
        # Processing treaming responses
        # Each chunk can be be either a string or contain JSON. 
        # If the chunk is a string it is a status action update - "Critic evaluates the text". 
        # If it is a JSON it will contain the generated blog post content.
        with requests.post(url, json=payload, headers={}, stream=True) as response:
            for line in response.iter_lines():
                result = line.decode('utf-8')
                # For each line as JSON
                # result = json.loads(line.decode('utf-8'))
                if not is_valid_json(result):
                   status.write(result)  
                   
        status.update(label="Backend call complete", state="complete", expanded=False)
    except Exception as e:
        status.update(
            label=f"Backend call failed: {e}", state="complete", expanded=False
        )
        
st.markdown(json.loads(result)["content"])
