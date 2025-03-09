import logging
from flask import Blueprint, request, jsonify
from db.chroma_db import get_player_collection, validate_cricket_query
from services.player_service import update_csv_data, search_player_by_name, format_player_info, format_player_list
from services.gemini_service import get_gemini_response, model

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint
chatbot_bp = Blueprint("chatbot", __name__)


@chatbot_bp.route("/", methods=["GET"])
def home():
    return jsonify({"status": "online", "message": "Cricket Chatbot is Running!"})


@chatbot_bp.route("/api/update-player-data", methods=["POST"])
def update_player_data():
    """API endpoint to receive player data from Node.js backend"""
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided"
            })

        # Update CSV file
        csv_update_success = update_csv_data(data)

        # Reinitialize ChromaDB with updated data
        if csv_update_success:
            # Force refresh the player collection by clearing the LRU cache
            collection = get_player_collection(force_refresh=True)
            if collection:
                return jsonify({
                    "success": True,
                    "message": "Player data updated in RAG database successfully"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "CSV updated but failed to update ChromaDB"
                })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to update player data in CSV"
            })

    except Exception as e:
        logger.error(f"Error in update_player_data: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        })


@chatbot_bp.route("/query/", methods=["GET"])
def query_chatbot():
    query = request.args.get("query", "").strip()

    if not query:
        return jsonify({"response": "Please provide a query."})

    # Handle greetings and general chat
    query_lower = query.lower()
    greeting_words = ["hi", "hello", "hey", "greetings", "hola"]

    if any(word == query_lower for word in greeting_words):
        response = "Hello! Welcome to SpiritxBot. I can help you with cricket player information. Ask me about players, batsmen, bowlers, all-rounders, or the best cricket team!"
        return jsonify({"response": response})

    if not validate_cricket_query(query):
        return jsonify({
            "response": "I only provide information about cricket players and teams. Please ask me about cricket players, statistics, or teams."})

    collection = get_player_collection()
    if not collection:
        return jsonify({"response": "Error accessing player database. Please try again later."})

    try:
        # Get all players for filtering and analysis
        players_result = collection.get()
        if not players_result or not players_result['metadatas']:
            return jsonify({"response": "No players found in the database."})

        players = players_result['metadatas']

        # Convert numeric fields to integers for proper sorting and comparison
        for player in players:
            try:
                # Convert runs to int
                player['total_runs'] = int(player.get('total_runs', player.get('Total Runs', 0)))
                player['Total Runs'] = player['total_runs']

                # Convert wickets to int
                player['wickets'] = int(player.get('wickets', player.get('Wickets', 0)))
                player['Wickets'] = player['wickets']

                # Convert base price to int
                player['base_price'] = int(player.get('base_price', player.get('Base Price', 0)))
                player['Base Price'] = player['base_price']

                # Extract other fields for consistency
                player['name'] = player.get('name', player.get('Name', ''))
                player['Name'] = player['name']

                player['category'] = player.get('category', player.get('Category', ''))
                player['Category'] = player['category']

                player['role'] = player.get('role', player.get('Role', ''))
                player['Role'] = player['role']

                # Add other fields
                player['runs_conceded'] = int(player.get('runs_conceded', player.get('Runs Conceded', 0)))
                player['Runs Conceded'] = player['runs_conceded']

                player['innings_played'] = int(player.get('innings_played', player.get('Innings Played', 0)))
                player['Innings Played'] = player['innings_played']

                player['overs_bowled'] = float(player.get('overs_bowled', player.get('Overs Bowled', 0)))
                player['Overs Bowled'] = player['overs_bowled']
            except (ValueError, TypeError) as e:
                logger.warning(f"Error converting player stats: {str(e)}")

        # Player search by name
        if "player" in query_lower and any(name in query_lower for name in [p['name'].lower() for p in players]):
            # Use Gemini to understand the query better
            gemini_analysis = None
            if model:
                try:
                    prompt = f"""
                    Analyze this cricket player search query: "{query}"
                    Extract the player name the user is looking for.
                    Return ONLY the player name, nothing else.
                    """
                    gemini_analysis = model.generate_content(prompt).text.strip()
                except Exception as e:
                    logger.error(f"Error analyzing query with Gemini: {str(e)}")

            # If Gemini couldn't help, try direct matching
            if not gemini_analysis:
                for player in players:
                    if player['name'].lower() in query_lower:
                        gemini_analysis = player['name']
                        break

            if gemini_analysis:
                matched_players = search_player_by_name(players, gemini_analysis)
                if matched_players:
                    # Use Gemini to generate a better response
                    if model and len(matched_players) == 1:
                        context = matched_players[0]
                        response = get_gemini_response(f"Tell me about {matched_players[0]['name']}", context)
                        if response:
                            return jsonify({"response": response})

                    # If Gemini response wasn't generated, format a readable response manually
                    if len(matched_players) == 1:
                        formatted_response = format_player_info(matched_players[0])
                        return jsonify({"response": formatted_response})
                    else:
                        # Multiple players matched - create a readable list
                        player_names = [p['name'] for p in matched_players]
                        formatted_response = f"I found multiple players matching that name: {', '.join(player_names)}. Could you please specify which one you're interested in?"
                        return jsonify({"response": formatted_response})

        # Best batsman query
        if "best batsman" in query_lower:
            # Sort by runs, then by base price as a tiebreaker
            sorted_batsmen = sorted(
                [p for p in players if p['role'].lower() == 'batsman'],
                key=lambda p: (p['total_runs'], p['base_price']),
                reverse=True
            )

            # Get the best batsman
            if sorted_batsmen:
                best_batsman = sorted_batsmen[0]

                # Use Gemini to enhance the response
                if model:
                    context = best_batsman
                    response = get_gemini_response("Who is the best batsman?", context)
                    if response:
                        return jsonify({"response": response})

                # Fallback to formatted response if Gemini fails
                formatted_response = f"""
                The best batsman is {best_batsman['name']} with {best_batsman['total_runs']} runs.
                Base Price: ₹{best_batsman['base_price']:,}

                {format_player_info(best_batsman)}
                """
                return jsonify({"response": formatted_response})
            else:
                return jsonify({"response": "No specialized batsmen found in the database."})

        # Best bowler query
        elif "best bowler" in query_lower:
            # Sort by wickets, then by base price as a tiebreaker
            sorted_bowlers = sorted(
                [p for p in players if p['role'].lower() == 'bowler'],
                key=lambda p: (p['wickets'], p['base_price']),
                reverse=True
            )

            # Get the best bowler
            if sorted_bowlers:
                best_bowler = sorted_bowlers[0]

                # Use Gemini to enhance the response
                if model:
                    context = best_bowler
                    response = get_gemini_response("Who is the best bowler?", context)
                    if response:
                        return jsonify({"response": response})

                # Fallback to formatted response if Gemini fails
                formatted_response = f"""
                The best bowler is {best_bowler['name']} with {best_bowler['wickets']} wickets.
                Base Price: ₹{best_bowler['base_price']:,}

                {format_player_info(best_bowler)}
                """
                return jsonify({"response": formatted_response})
            else:
                return jsonify({"response": "No specialized bowlers found in the database."})

        # Best all-rounder query
        elif "best all-rounder" in query_lower or "best all rounder" in query_lower or "best allrounder" in query_lower:
            # Define a scoring function for all-rounders
            def all_rounder_score(player):
                # Simple metric: sum of runs and wickets*10 (typical cricket weighting)
                return player['total_runs'] + (player['wickets'] * 10)

            # Sort all-rounders by our scoring function, then by base price as tiebreaker
            sorted_all_rounders = sorted(
                [p for p in players if p['role'].lower() == 'all-rounder'],
                key=lambda p: (all_rounder_score(p), p['base_price']),
                reverse=True
            )

            if sorted_all_rounders:
                best_all_rounder = sorted_all_rounders[0]

                # Use Gemini to enhance the response
                if model:
                    context = best_all_rounder
                    response = get_gemini_response("Who is the best all-rounder?", context)
                    if response:
                        return jsonify({"response": response})

                # Fallback to formatted response if Gemini fails
                formatted_response = f"""
                The best all-rounder is {best_all_rounder['name']} with {best_all_rounder['total_runs']} runs and {best_all_rounder['wickets']} wickets.
                Base Price: ₹{best_all_rounder['base_price']:,}

                {format_player_info(best_all_rounder)}
                """
                return jsonify({"response": formatted_response})
            else:
                return jsonify({"response": "No all-rounders found in the database."})

        # Best players query
        elif "best players" in query_lower:
            # Sort players primarily by base price in descending order
            sorted_players = sorted(
                players,
                key=lambda p: p['base_price'],
                reverse=True
            )

            # Use Gemini to enhance the response
            if model and sorted_players:
                context = sorted_players[:5]  # Use top 5 players as context
                response = get_gemini_response("Who are the best cricket players?", context)
                if response:
                    return jsonify({"response": response})

            # Fallback to formatted response if Gemini fails
            top_players = sorted_players[:10]
            formatted_response = "Here are the top cricket players based on their value:\n\n"
            for i, player in enumerate(top_players, 1):
                formatted_response += f"{i}. {player['name']} - {player['role']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}, Wickets: {player['wickets']}\n"

            return jsonify({"response": formatted_response})

        # Best team query
        elif "best team" in query_lower:
            # Sort all players primarily by base price in descending order
            sorted_by_price = sorted(players, key=lambda p: p['base_price'], reverse=True)

            # Identify players by role
            batsmen = [p for p in sorted_by_price if p['role'].lower() == 'batsman']
            bowlers = [p for p in sorted_by_price if p['role'].lower() == 'bowler']
            all_rounders = [p for p in sorted_by_price if p['role'].lower() == 'all-rounder']

            # Build a balanced team of 11 players based on value and role
            team = []
            player_ids = set()  # To avoid duplicates

            # Add top batsmen (prioritizing value)
            for player in batsmen:
                if len(team) >= 5:
                    break
                if player['name'] not in player_ids:
                    team.append(player)
                    player_ids.add(player['name'])

            # Add top all-rounders (crucial for balance)
            for player in all_rounders:
                if len(team) >= 7:
                    break
                if player['name'] not in player_ids:
                    team.append(player)
                    player_ids.add(player['name'])

            # Add top bowlers
            for player in bowlers:
                if len(team) >= 11:
                    break
                if player['name'] not in player_ids:
                    team.append(player)
                    player_ids.add(player['name'])

            # If we still need players and have more all-rounders, add them
            if len(team) < 11 and all_rounders:
                for player in all_rounders:
                    if len(team) >= 11:
                        break
                    if player['name'] not in player_ids:
                        team.append(player)
                        player_ids.add(player['name'])

            # If still need players, add more batsmen or bowlers
            remaining_players = [p for p in sorted_by_price if p['name'] not in player_ids]

            for player in remaining_players:
                if len(team) >= 11:
                    break
                team.append(player)
                player_ids.add(player['name'])

            # Use Gemini to enhance the response
            if model and team:
                context = team
                response = get_gemini_response("Create the best cricket team with these players", context)
                if response:
                    return jsonify({"response": response})

            # Fallback to formatted response if Gemini fails
            formatted_response = "Here's the best cricket team based on player value and role:\n\n"
            formatted_response += "BATSMEN:\n"
            for player in [p for p in team if p['role'].lower() == 'batsman']:
                formatted_response += f"- {player['name']} (Base Price: ₹{player['base_price']:,}, Runs: {player['total_runs']})\n"

            formatted_response += "\nBOWLERS:\n"
            for player in [p for p in team if p['role'].lower() == 'bowler']:
                formatted_response += f"- {player['name']} (Base Price: ₹{player['base_price']:,}, Wickets: {player['wickets']})\n"

            formatted_response += "\nALL-ROUNDERS:\n"
            for player in [p for p in team if p['role'].lower() == 'all-rounder']:
                formatted_response += f"- {player['name']} (Base Price: ₹{player['base_price']:,}, Runs: {player['total_runs']}, Wickets: {player['wickets']})\n"

            return jsonify({"response": formatted_response})

        # Player type queries - individual types
        elif "batsmen" in query_lower or "batsman list" in query_lower:
            # Return top batsmen by base price
            sorted_batsmen = sorted(
                [p for p in players if p['role'].lower() == 'batsman'],
                key=lambda p: p['base_price'],
                reverse=True
            )

            top_batsmen = sorted_batsmen[:10]

            # Use Gemini for enhanced response
            if model and top_batsmen:
                context = top_batsmen
                response = get_gemini_response("List the top batsmen in cricket", context)
                if response:
                    return jsonify({"response": response})

            # Fallback formatted response
            formatted_response = "Top Batsmen by Value:\n\n"
            for i, player in enumerate(top_batsmen, 1):
                formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}\n"

            return jsonify({"response": formatted_response})

        elif "bowlers" in query_lower or "bowler list" in query_lower:
            # Return top bowlers by base price
            sorted_bowlers = sorted(
                [p for p in players if p['role'].lower() == 'bowler'],
                key=lambda p: p['base_price'],
                reverse=True
            )

            top_bowlers = sorted_bowlers[:10]

            # Use Gemini for enhanced response
            if model and top_bowlers:
                context = top_bowlers
                response = get_gemini_response("List the top bowlers in cricket", context)
                if response:
                    return jsonify({"response": response})

            # Fallback formatted response
            formatted_response = "Top Bowlers by Value:\n\n"
            for i, player in enumerate(top_bowlers, 1):
                formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Wickets: {player['wickets']}\n"

            return jsonify({"response": formatted_response})

        elif "all-rounders" in query_lower or "all rounders" in query_lower or "allrounders" in query_lower:
            # Return top all-rounders by base price
            sorted_all_rounders = sorted(
                [p for p in players if p['role'].lower() == 'all-rounder'],
                key=lambda p: p['base_price'],
                reverse=True
            )

            top_all_rounders = sorted_all_rounders[:10]

            # Use Gemini for enhanced response
            if model and top_all_rounders:
                context = top_all_rounders
                response = get_gemini_response("List the top all-rounders in cricket", context)
                if response:
                    return jsonify({"response": response})

            # Fallback formatted response
            formatted_response = "Top All-Rounders by Value:\n\n"
            for i, player in enumerate(top_all_rounders, 1):
                formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}, Wickets: {player['wickets']}\n"

            return jsonify({"response": formatted_response})

        # Combined player types query
        elif "players" in query_lower:
            # Use Gemini to understand what types of players the user wants
            player_types = []
            if model:
                try:
                    prompt = f"""
                    Analyze this cricket query: "{query}"
                    What types of players is the user asking for? Choose from: batsmen, bowlers, all-rounders.
                    If multiple types are mentioned, list them all separated by commas.
                    Return ONLY the player types, nothing else.
                    """
                    player_types_text = model.generate_content(prompt).text.strip()
                    player_types = [t.strip().lower() for t in player_types_text.split(',')]
                except Exception as e:
                    logger.error(f"Error analyzing query with Gemini: {str(e)}")

            # If Gemini failed or didn't detect specific types, check for keywords
            if not player_types:
                if "batsman" in query_lower or "batsmen" in query_lower:
                    player_types.append("batsmen")
                if "bowler" in query_lower or "bowlers" in query_lower:
                    player_types.append("bowlers")
                if "all-rounder" in query_lower or "all rounder" in query_lower or "allrounder" in query_lower:
                    player_types.append("all-rounders")

            # If we've identified specific player types
            if player_types:
                result = {}
                formatted_response = "Here are the players you asked about:\n\n"

                if "batsmen" in player_types:
                    sorted_batsmen = sorted(
                        [p for p in players if p['role'].lower() == 'batsman'],
                        key=lambda p: p['base_price'],
                        reverse=True
                    )
                    result["batsmen"] = sorted_batsmen[:5]
                    formatted_response += "Top Batsmen by Value:\n"
                    for i, player in enumerate(sorted_batsmen[:5], 1):
                        formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}\n"
                    formatted_response += "\n"

                if "bowlers" in player_types:
                    sorted_bowlers = sorted(
                        [p for p in players if p['role'].lower() == 'bowler'],
                        key=lambda p: p['base_price'],
                        reverse=True
                    )
                    result["bowlers"] = sorted_bowlers[:5]
                    formatted_response += "Top Bowlers by Value:\n"
                    for i, player in enumerate(sorted_bowlers[:5], 1):
                        formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Wickets: {player['wickets']}\n"
                    formatted_response += "\n"

                if "all-rounders" in player_types:
                    sorted_all_rounders = sorted(
                        [p for p in players if p['role'].lower() == 'all-rounder'],
                        key=lambda p: p['base_price'],
                        reverse=True
                    )
                    result["all_rounders"] = sorted_all_rounders[:5]
                    formatted_response += "Top All-Rounders by Value:\n"
                    for i, player in enumerate(sorted_all_rounders[:5], 1):
                        formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}, Wickets: {player['wickets']}\n"

                # Use Gemini to create a meaningful response
                if model and result:
                    response = get_gemini_response(f"Show information about cricket {', '.join(player_types)}", result)
                    if response:
                        return jsonify({"response": response})

                return jsonify({"response": formatted_response})

            # If no specific types identified, return top players of each type
            else:
                # Sort players by role and base price
                batsmen = sorted(
                    [p for p in players if p['role'].lower() == 'batsman'],
                    key=lambda p: p['base_price'],
                    reverse=True
                )[:5]

                bowlers = sorted(
                    [p for p in players if p['role'].lower() == 'bowler'],
                    key=lambda p: p['base_price'],
                    reverse=True
                )[:5]

                all_rounders = sorted(
                    [p for p in players if p['role'].lower() == 'all-rounder'],
                    key=lambda p: p['base_price'],
                    reverse=True
                )[:5]

                # Use Gemini to create a meaningful response
                if model:
                    result = {
                        "batsmen": batsmen,
                        "bowlers": bowlers,
                        "all_rounders": all_rounders
                    }
                    response = get_gemini_response("Show information about top cricket players of all types", result)
                    if response:
                        return jsonify({"response": response})

                # Fallback formatted response
                formatted_response = "Here are the top cricket players across all categories by value:\n\n"

                formatted_response += "Top Batsmen:\n"
                for i, player in enumerate(batsmen, 1):
                    formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}\n"

                formatted_response += "\nTop Bowlers:\n"
                for i, player in enumerate(bowlers, 1):
                    formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Wickets: {player['wickets']}\n"

                formatted_response += "\nTop All-Rounders:\n"
                for i, player in enumerate(all_rounders, 1):
                    formatted_response += f"{i}. {player['name']} - Base Price: ₹{player['base_price']:,} - Runs: {player['total_runs']}, Wickets: {player['wickets']}\n"

                return jsonify({"response": formatted_response})

        # Default to Gemini for understanding the user's query
        if model:
            try:
                gemini_query = f"""
                Analyze this cricket query: "{query}"
                What is the user looking for? (player search, stats comparison, team information, etc.)
                """
                query_analysis = model.generate_content(gemini_query).text

                # Try to get results based on Gemini's analysis
                # First try ChromaDB for vector search
                results = collection.query(query_texts=[query], n_results=3)
                if results and results['metadatas'] and results['metadatas'][0]:
                    # Use Gemini to generate a response based on query and results
                    context = results['metadatas'][0]
                    response = get_gemini_response(query, context)
                    if response:
                        return jsonify({"response": response})

                    # Fallback format response
                    formatted_response = format_player_info(results['metadatas'][0])
                    return jsonify({"response": formatted_response})
            except Exception as e:
                logger.error(f"Error with Gemini analysis: {str(e)}")

        # If we reach here, try a basic vector search
        results = collection.query(query_texts=[query], n_results=1)
        if results and results['metadatas'] and results['metadatas'][0]:
            # Format the response instead of returning raw JSON
            formatted_response = format_player_info(results['metadatas'][0])
            return jsonify({"response": formatted_response})

        return jsonify({
            "response": "I couldn't find the information you're looking for. Please try asking about specific cricket players, teams, or statistics."})

    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return jsonify({"response": "An error occurred while processing your request."})