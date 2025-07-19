⚙️ Configuration Overview
features_config.json
🔐 vault_enabled / wagers_enabled

    Description: Toggles the Vault and Wager systems.

    How to set: Use the /enable_vault command.

    Important: All members must have their fantasy_ids and discord_tags bound before enabling.

👋 slaps_enabled

    Description: Enables slap interactions in a specific channel.

    How to set: Use the /set_slap_channel command.

📰 news_enabled

    Description: Enables player news updates.

    How to set: Use the /set_news command.

💸 transactions_enabled

    Description: Enables transaction announcements.

    How to set: Use the /set_transactions_channel command.

⚙️ trade_value_config.json

    Description: Contains settings that influence trade value calculations.
    
    How to set: Must be configured manually.
    
    Fields:
    
        "Dynasty": "True" or "False" – whether the league is dynasty format.
    
        "numQbs": Integer – number of starting quarterbacks (e.g., 1 for standard, 2 for superflex).
    
        "numTeams": Integer – total number of teams in the league.
    
        "ppr": Float – points per reception (0, 0.5, or 1 typically).

⚙️ challenge_config.json

    Description: Contains settings related to slap challenges and wager fund distribution.
    
    How to set: Must be configured manually.
    
    Fields include:
    
        Wager Fund Distribution: Defines how wagered funds are split among participants.
    
        Role Names: Customizable role names for challenge winners and losers.
    
        GIF Links: All GIF URLs used for animations and visual feedback during slap challenges.
        
