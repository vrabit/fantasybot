# 🏈 FantasyBot
A Discord bot used for my Yahoo Fantasy Football leagues.

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)


## Features

- 🏆 Fantasy standings and weekly recaps  
- 📊 Player stat lookups and trade value comparisons  
- 📢 NFL news integration via RSS feeds  
- 🤖 Fun Discord commands like `/slap`  
- 💬 Slash command interface (no prefix spam)


## Slash Commands
| Command           | Description                                 | Input                        |
| ----------------- | ------------------------------------------- | ---------------------------- |
| `/week_chump`     | Loser of the specified week                 | `week: int`                  |
| `/chump`          | Loser of the current week                   | –                            |
| `/week_mvp`       | MVP of the specified week                   | `week: int`                  |
| `/mvp`            | MVP of the current week                     | –                            |
| `/week_matchups`  | Matchups of the specified week              | `week: int`                  |
| `/matchups`       | Matchups of the current week                | –                            |
| `/leaderboard`    | Fantasy leaderboard                         | –                            |
| `/most_points`    | Standings by most points                    | –                            |
| `/points_against` | Standings by points against                 | –                            |
| `/recap`          | Last week's recap                           | –                            |
| `/player_stats`   | NFL player details                          | `player_name: str`           |
| `/slap`           | Slap a user. Loser = Chump, Denier = Coward | `discord_user: discord.User` |
| `/trade_send`     | Add player to sender side for trade         | `player: str`                |
| `/trade_receive`  | Add player to receiver side for trade       | `player: str`                |
| `/compare_value`  | Evaluate trade value                        | –                            |
| `/clear_trade`    | Clear your current trade proposals          | –                            |


## 🚀 Quick Start

### Prerequisites
   - Create a [Discord bot](https://discord.com/developers/applications)
   - Register a [Yahoo Fantasy Sports app](https://developer.yahoo.com/apps/)
   - Aquire your [Yahoo Fantasy Football League ID](https://football.fantasysports.yahoo.com/)

<details markdown="1">
   
<summary>📌⚙️ Setup Instructions</summary>

---

1. Clone the repo:

   ```bash
   git clone https://github.com/vrabit/fantasybot.git
   
   ```


---

2. Install Requirements: 

   ```bash
   pip install -r requirements.txt

   ```

---

3. Create a Yahoo Fantasy Sports app
    - Go to the [Yahoo Developer Dashboard](https://developer.yahoo.com/apps/)
    - Click "Create an App"
    - Set:
        - Application Name: `(any name you want)`
        - OAuth Client Type: `Confidential Client`
        - Permissions: check `Fantasy Sports`

    - After creation, save your `Client ID` and `Client Secret`
    - Set a placeholder Redirect URI, such as `https://localhost/` (you won't need to host this)

---

4. Rename and configure your Yahoo app credentials

    - In the `yfpyauth/` directory, rename:
    `.env.private.example` → `.env.private`

    - Open `.env.private` and fill in the credentials from your Yahoo Developer app:

   ```env
    CONSUMER_KEY=<YAHOO_API_KEY>
    CONSUMER_SECRET=<YAHOO_API_SECRET>
   ```
---

5. Get your Yahoo Fantasy Football League ID

    - Go to your Yahoo Fantasy Football league in a browser

    - Look at the URL — your League ID will appear like this:
    `https://football.fantasysports.yahoo.com/f1/123456` → Your League ID is 123456

---

6. Rename and configure your environment file

    - In the `yfpyauth/` directory, rename:
    `.env.config.example` → `.env.config`

    - Open `.env.config` and set the following values:

    ```env
    LEAGUE_ID=<YOUR_LEAGUE_ID>
    GAME_CODE=NFL
    GAME_ID= # Leave empty to default to the current NFL season
   
    ```
---

7. Set up your Discord bot

   - Create a new [Discord bot application](https://discord.com/developers/applications)

     
    - Generate an invite link using the correct OAuth scopes and permissions (e.g., via the Discord Permissions Calculator)

       <details> <summary>📌🔐 Required Permissions</summary>
          
         | Action                   | Permission Name                        | Hex Value    |
         | ------------------------ | -------------------------------------- | ------------ |
         | Slash command usage      | `applications.commands` *(scope only)* | –            |
         | Send messages            | `Send Messages`                        | `0x00000800` |
         | Read message history     | `Read Message History`                 | `0x00010000` |
         | Manage roles             | `Manage Roles`                         | `0x10000000` |
         | Create public threads    | `Create Public Threads`                | `0x00010000` |
         | Create private threads   | `Create Private Threads`               | `0x00020000` |
         | Send messages in threads | `Send Messages in Threads`             | `0x00040000` |
         | Send embedded messages   | `Embed Links`                          | `0x00004000` |
   
       </details>

    - Invite the bot to your server

---

8.
    In the `discordauth/` directory, rename:
    `.env.discord.example` → `.env.discord`

    Fill in your Discord bot credentials:

     ```env
    DISCORD_TOKEN=<YOUR_DISCORD_BOT_TOKEN>
    APP_ID=<YOUR_DISCORD_APP_ID>
    GUILD_ID=<YOUR_DISCORD_SERVER_ID>

     ```

    ⚠️ GUILD_ID is needed for registering slash commands in a development/test server.
    
</details>
