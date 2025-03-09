import logging
import google.generativeai as genai
from config import Config

# Set up logging
logger = logging.getLogger(__name__)

# Configure Gemini AI
try:
    if Config.GEMINI_API_KEY:
        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-pro")
    else:
        logger.warning("GEMINI_API_KEY not found. Ensure it is set in .env file.")
        model = None
except Exception as e:
    logger.error(f"Error configuring Gemini AI: {str(e)}")
    model = None

def get_gemini_response(query, context=None):
    """Get enhanced response from Gemini model"""
    if not model:
        return None

    try:
        # Create a prompt that includes context if available
        prompt = query
        if context:
            prompt = f"""
            Given this cricket data: {context}

            Please provide a meaningful and conversational response to the user query: {query}

            FORMAT REQUIREMENTS:
            - Format the response in a friendly, readable way
            - Highlight key statistics in a natural way
            - DO NOT return JSON or technical formats
            - Use natural language as if you're having a conversation
            - Focus only on the data provided
            - IMPORTANT: DO NOT mention player points or reference any point calculations
            - When referring to pricing, use the term "base price" or "value" instead
            """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error getting Gemini response: {str(e)}")
        return None