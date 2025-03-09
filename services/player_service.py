import logging
import os
import pandas as pd
from config import Config
from db.chroma_db import get_player_collection

# Set up logging
logger = logging.getLogger(__name__)


def update_csv_data(player_data):
    """Update the CSV file with new player data from Node.js backend"""
    try:
        csv_file_path = Config.DATASET_PATH
        df = None

        # Check if file exists and load it
        if os.path.exists(csv_file_path):
            df = pd.read_csv(csv_file_path)
        else:
            # Create new dataframe with necessary columns
            df = pd.DataFrame(columns=[
                'Name', 'University', 'Category', 'Total Runs', 'Balls Faced',
                'Innings Played', 'Wickets', 'Overs Bowled', 'Runs Conceded',
                'Base Price'
            ])

        # Handle player deletion
        if player_data.get('deletePlayer'):
            player_name = player_data.get('name')
            if player_name:
                df = df[df['Name'] != player_name]
                logger.info(f"Deleted player {player_name} from CSV")
            else:
                logger.warning("Player deletion requested but no name provided")

            # Save updated dataframe
            df.to_csv(csv_file_path, index=False)
            return True

        # Handle multiple players
        if 'players' in player_data:
            for player in player_data['players']:
                _update_single_player(df, player, csv_file_path)
            return True

        # Handle single player
        return _update_single_player(df, player_data, csv_file_path)

    except Exception as e:
        logger.error(f"Error updating CSV data: {str(e)}")
        return False


def _update_single_player(df, player_data, csv_file_path):
    """Helper function to update a single player in the dataframe"""
    try:
        player_id = player_data.get('playerId')
        player_name = player_data.get('name')
        tournament_data = player_data.get('tournamentData', {})

        if not player_name:
            logger.warning("No player name provided, skipping update")
            return False

        # Extract data
        total_runs = tournament_data.get('runs', 0)
        balls_faced = tournament_data.get('ballsFaced', 0)
        innings_played = tournament_data.get('inningsPlayed', 0)
        wickets = tournament_data.get('wickets', 0)
        overs_bowled = tournament_data.get('oversBowled', 0)
        runs_conceded = tournament_data.get('runsConceded', 0)
        category = player_data.get('category', '')
        base_price = player_data.get('basePrice', 0)

        # Determine if player exists in the dataframe
        existing_player = df[df['Name'] == player_name]

        if len(existing_player) > 0:
            # Update existing player
            df.loc[df['Name'] == player_name, 'Total Runs'] = total_runs
            df.loc[df['Name'] == player_name, 'Balls Faced'] = balls_faced
            df.loc[df['Name'] == player_name, 'Innings Played'] = innings_played
            df.loc[df['Name'] == player_name, 'Wickets'] = wickets
            df.loc[df['Name'] == player_name, 'Overs Bowled'] = overs_bowled
            df.loc[df['Name'] == player_name, 'Runs Conceded'] = runs_conceded
            df.loc[df['Name'] == player_name, 'Category'] = category
            df.loc[df['Name'] == player_name, 'Base Price'] = base_price
            logger.info(f"Updated player {player_name} in CSV")
        else:
            # Add new player
            new_row = {
                'Name': player_name,
                'University': '',  # Default value
                'Category': category,
                'Total Runs': total_runs,
                'Balls Faced': balls_faced,
                'Innings Played': innings_played,
                'Wickets': wickets,
                'Overs Bowled': overs_bowled,
                'Runs Conceded': runs_conceded,
                'Base Price': base_price
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            logger.info(f"Added new player {player_name} to CSV")

        # Save updated dataframe
        df.to_csv(csv_file_path, index=False)
        return True

    except Exception as e:
        logger.error(f"Error updating single player in CSV: {str(e)}")
        return False


def search_player_by_name(players, name_query):
    """Search for players by name"""
    name_query = name_query.lower()
    matched_players = []

    for player in players:
        if name_query in player['name'].lower():
            matched_players.append(player)

    return matched_players


def format_player_info(player):
    """Format player information into readable text"""
    # Don't include player points in the response
    return f"""
    Player: {player['name']}
    University: {player['university']}
    Category: {player['category']}
    Role: {player['role']}
    Base Price: ₹{int(player.get('base_price', 0)):,}
    Stats:
      - Total Runs: {player['total_runs']}
      - Wickets: {player['wickets']}
      - Innings Played: {player['innings_played']}
      - Overs Bowled: {player['overs_bowled']}
      - Runs Conceded: {player['runs_conceded']}

    {player['name']} is a {player['role']} who has scored {player['total_runs']} runs and taken {player['wickets']} wickets.
    """


def format_player_list(players, description):
    """Format a list of players into readable text"""
    formatted_text = f"\n{description}:\n\n"
    for i, player in enumerate(players, 1):
        # Don't include player points in the response
        formatted_text += f"{i}. {player['name']} - {player['role']} - Base Price: ₹{int(player.get('base_price', 0)):,} - Runs: {player['total_runs']}, Wickets: {player['wickets']}\n"
    return formatted_text