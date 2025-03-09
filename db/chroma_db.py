import logging
import os
import pandas as pd
import chromadb
import numpy as np
from chromadb.utils import embedding_functions
from functools import lru_cache
from config import Config

# Set up logging
logger = logging.getLogger(__name__)


def classify_player_role(player_data):
    """Classify a player's role based on their stats"""
    runs = int(player_data.get('Total Runs', 0)) if pd.notna(player_data.get('Total Runs', 0)) else 0
    wickets = int(player_data.get('Wickets', 0)) if pd.notna(player_data.get('Wickets', 0)) else 0

    if wickets > 5 and runs < 50:
        return 'Bowler'
    elif runs > 100 and wickets < 3:
        return 'Batsman'
    else:
        return 'All-Rounder'


def validate_cricket_query(query):
    """Validate if a query is related to cricket"""
    cricket_keywords = [
        'cricket', 'player', 'batsman', 'bowler', 'all-rounder', 'allrounder',
        'team', 'runs', 'wickets', 'innings', 'stats', 'statistics', 'batting',
        'bowling', 'score', 'match', 'tournament', 'performance', 'best'
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in cricket_keywords)


# Helper function to safely convert values to int or float
def safe_convert(value, convert_type=int, default=0):
    """Safely convert a value to int or float, handling NaN and None cases"""
    if pd.isna(value) or value is None:
        return default
    try:
        return convert_type(value)
    except (ValueError, TypeError):
        return default


@lru_cache(maxsize=1)
def get_player_collection(force_refresh=False):
    """Get or create the ChromaDB collection for cricket players"""
    try:
        # Initialize client
        persist_directory = Config.CHROMA_PERSIST_DIRECTORY
        collection_name = Config.COLLECTION_NAME

        # Create directory if it doesn't exist
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)

        # Create client
        client = chromadb.PersistentClient(path=persist_directory)

        # Get or create collection
        embedding_function = embedding_functions.DefaultEmbeddingFunction()

        # If force refresh, delete the collection if it exists
        if force_refresh:
            try:
                client.delete_collection(name=collection_name)
                logger.info(f"Deleted collection {collection_name} for refresh")
            except Exception as e:
                logger.warning(f"No collection to delete or error: {str(e)}")

        # Create or get collection
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function
        )

        # Load player data from CSV
        csv_file_path = Config.DATASET_PATH
        if not os.path.exists(csv_file_path):
            logger.warning(f"CSV file not found at {csv_file_path}")
            return collection

        df = pd.read_csv(csv_file_path)

        # Check if collection is empty or force refresh requested
        if collection.count() == 0 or force_refresh:
            # Clear collection if needed (already done if force_refresh was True)
            if collection.count() > 0 and force_refresh:
                collection.delete(where={})

            # Prepare data for insertion
            documents = []
            metadatas = []
            ids = []

            for index, row in df.iterrows():
                player_id = f"player_{index}"

                # Determine player role based on stats
                player_role = classify_player_role(row)

                # Create document text
                document = f"""
                Player: {row['Name']}
                University: {row.get('University', '')}
                Category: {row.get('Category', '')}
                Role: {player_role}
                Total Runs: {safe_convert(row.get('Total Runs', 0))}
                Balls Faced: {safe_convert(row.get('Balls Faced', 0))}
                Innings Played: {safe_convert(row.get('Innings Played', 0))}
                Wickets: {safe_convert(row.get('Wickets', 0))}
                Overs Bowled: {safe_convert(row.get('Overs Bowled', 0), float)}
                Runs Conceded: {safe_convert(row.get('Runs Conceded', 0))}
                Base Price: {safe_convert(row.get('Base Price', 0))}
                """

                # Create metadata with safe conversions
                metadata = {
                    'name': str(row['Name']),
                    'university': str(row.get('University', '')),
                    'category': str(row.get('Category', '')),
                    'role': str(player_role),
                    'total_runs': safe_convert(row.get('Total Runs', 0)),
                    'balls_faced': safe_convert(row.get('Balls Faced', 0)),
                    'innings_played': safe_convert(row.get('Innings Played', 0)),
                    'wickets': safe_convert(row.get('Wickets', 0)),
                    'overs_bowled': safe_convert(row.get('Overs Bowled', 0), float),
                    'runs_conceded': safe_convert(row.get('Runs Conceded', 0)),
                    'base_price': safe_convert(row.get('Base Price', 0))
                }

                documents.append(document)
                metadatas.append(metadata)
                ids.append(player_id)

            # Add data to collection in batches
            if documents:
                batch_size = 100
                for i in range(0, len(documents), batch_size):
                    batch_end = min(i + batch_size, len(documents))
                    collection.add(
                        documents=documents[i:batch_end],
                        metadatas=metadatas[i:batch_end],
                        ids=ids[i:batch_end]
                    )
                logger.info(f"Added {len(documents)} players to ChromaDB collection")

        return collection

    except Exception as e:
        logger.error(f"Error initializing ChromaDB: {str(e)}")
        return None