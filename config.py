import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Paths
    DATASET_PATH = os.getenv("DATASET_PATH", "data/players.csv")

    # ChromaDB settings
    CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", "chroma_db")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "cricket_players")