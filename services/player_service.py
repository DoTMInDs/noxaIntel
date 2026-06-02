class PlayerService:
    """Manages and serves statistics for top football players and team rosters."""

    _PLAYER_DB = {
        "Haaland": {
            "name": "Erling Haaland",
            "team": "Manchester City",
            "goals": 27,
            "assists": 5,
            "matches": 31,
            "rating": 7.82,
            "shots_per_game": 4.1,
            "pass_accuracy": "78.4%",
            "position": "Forward"
        },
        "Saka": {
            "name": "Bukayo Saka",
            "team": "Arsenal",
            "goals": 16,
            "assists": 9,
            "matches": 33,
            "rating": 7.74,
            "shots_per_game": 2.8,
            "pass_accuracy": "84.2%",
            "position": "Winger"
        },
        "Odegaard": {
            "name": "Martin Odegaard",
            "team": "Arsenal",
            "goals": 8,
            "assists": 10,
            "matches": 32,
            "rating": 7.68,
            "shots_per_game": 2.1,
            "pass_accuracy": "89.1%",
            "position": "Midfielder"
        },
        "Salah": {
            "name": "Mohamed Salah",
            "team": "Liverpool",
            "goals": 18,
            "assists": 10,
            "matches": 30,
            "rating": 7.61,
            "shots_per_game": 3.4,
            "pass_accuracy": "81.5%",
            "position": "Winger"
        },
        "Palmer": {
            "name": "Cole Palmer",
            "team": "Chelsea",
            "goals": 22,
            "assists": 11,
            "matches": 32,
            "rating": 7.89,
            "shots_per_game": 3.2,
            "pass_accuracy": "83.9%",
            "position": "Attacking Midfielder"
        },
        "Bellingham": {
            "name": "Jude Bellingham",
            "team": "Real Madrid",
            "goals": 19,
            "assists": 6,
            "matches": 28,
            "rating": 7.91,
            "shots_per_game": 2.2,
            "pass_accuracy": "88.7%",
            "position": "Midfielder"
        },
        "Vinicius": {
            "name": "Vinicius Junior",
            "team": "Real Madrid",
            "goals": 15,
            "assists": 5,
            "matches": 26,
            "rating": 7.85,
            "shots_per_game": 3.0,
            "pass_accuracy": "80.2%",
            "position": "Winger"
        },
        "Mbappe": {
            "name": "Kylian Mbappe",
            "team": "PSG",
            "goals": 27,
            "assists": 7,
            "matches": 29,
            "rating": 8.04,
            "shots_per_game": 4.6,
            "pass_accuracy": "83.6%",
            "position": "Forward"
        },
        "Kane": {
            "name": "Harry Kane",
            "team": "Bayern Munich",
            "goals": 36,
            "assists": 8,
            "matches": 32,
            "rating": 8.12,
            "shots_per_game": 4.3,
            "pass_accuracy": "79.8%",
            "position": "Forward"
        },
        "Foden": {
            "name": "Phil Foden",
            "team": "Manchester City",
            "goals": 19,
            "assists": 8,
            "matches": 33,
            "rating": 7.79,
            "shots_per_game": 3.1,
            "pass_accuracy": "87.5%",
            "position": "Midfielder"
        },
        "De bruyne": {
            "name": "Kevin De Bruyne",
            "team": "Manchester City",
            "goals": 4,
            "assists": 10,
            "matches": 18,
            "rating": 7.76,
            "shots_per_game": 2.0,
            "pass_accuracy": "85.3%",
            "position": "Midfielder"
        },
        "Messi": {
            "name": "Lionel Messi",
            "team": "Inter Miami",
            "goals": 12,
            "assists": 9,
            "matches": 11,
            "rating": 8.25,
            "shots_per_game": 3.8,
            "pass_accuracy": "86.1%",
            "position": "Forward"
        },
        "Ronaldo": {
            "name": "Cristiano Ronaldo",
            "team": "Al Nassr",
            "goals": 35,
            "assists": 11,
            "matches": 31,
            "rating": 7.95,
            "shots_per_game": 5.4,
            "pass_accuracy": "82.0%",
            "position": "Forward"
        }
    }

    @classmethod
    def get_player_stats(cls, player_name: str) -> dict:
        """Returns statistics for a specific player by name."""
        if not player_name:
            return None
        
        normalized = player_name.lower().strip()
        
        # Exact/Partial match check
        for key, data in cls._PLAYER_DB.items():
            if key.lower() in normalized or normalized in data["name"].lower():
                return data
                
        return None

    @classmethod
    def get_team_key_players(cls, team_name: str) -> list:
        """Returns top players for a specific team."""
        if not team_name:
            return []
        
        normalized = team_name.lower().strip()
        players = []
        for key, data in cls._PLAYER_DB.items():
            if normalized in data["team"].lower():
                players.append(data)
                
        # Sort by goals + assists desc
        players.sort(key=lambda x: x["goals"] + x["assists"], reverse=True)
        return players

    @classmethod
    def get_top_scorers(cls) -> list:
        """Returns a list of all players sorted by goals desc."""
        players = list(cls._PLAYER_DB.values())
        players.sort(key=lambda x: x["goals"], reverse=True)
        return players[:6]
