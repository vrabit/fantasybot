# 🏈 FantasyBot
A Discord bot that integrates with Yahoo Fantasy Football leagues, transforming how friends engage with their fantasy season.
FantasyBot can be self-hosted on various platforms, including low-cost devices like a Raspberry Pi.

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)

---

## ✨ Key Features

FantasyBot is designed to enhance your fantasy football experience with a suite of powerful, engaging, and unique features:

* 🏆**Comprehensive League Insights:**
    * **Live Matchup Scores:** Get up-to-date fantasy team points for all weekly matchups using the `/matchups` command. *Note: This provides fantasy team point totals*
    * **League Information:** Instantly fetch detailed league standings, schedules, and scores.
    * **Leaderboards:** Showcase weekly and season leaders (MVP) and bottom performers (Chump). 
    * **Player Stats:** Get up-to-date player statistics directly in Discord.
    * **Transactions & Polls:** Automatically post league transactions and easily create polls for specific trades (e.g., to vote on "Collusion?").
    * **Weekly/Season Recaps:** Get visual recaps of your league's performance, including:
        * Podium-style bar graphs with Yahoo team images for ranking.
        * Bump charts showcasing team rankings over the regular season.
        * A season recap bar chart GIF for cumulative points collected.

* 📊**Advanced Player Valuation (Powered by FantasyCalc API):**
    * **Trade Evaluation:** Seamlessly compare players' trade values using `/trade_send`, `/trade_receive`, and `/trade_evaluate` commands, generating a bar chart for quick visual assessment.

* 📢**Real-time News Feed (Rotowire RSS):**
    * Integrate Rotowire's RSS feed directly into a designated Discord channel for continuous fantasy news updates.

* 🎲**Engaging Wager System:**
    * **Slap Challenges:** Challenge another user's Yahoo team with a `/slap @discord_tag token_amount` command. At week's end, the fantasy points of both teams are compared, winner takes all!
    * **Matchup Wagering:** Bet your in-game tokens on any of the week's fantasy football matchups with `\wager`. If multiple users wager on the same winning team, the closest cumulative point prediction wins the pot.

---

## 🚀 Setup

### Prerequisites
   - Create a [Discord bot](https://discord.com/developers/applications)
   - Register a [Yahoo Fantasy Sports app](https://developer.yahoo.com/apps/)
   - Acquire your [Yahoo Fantasy Football League ID](https://football.fantasysports.yahoo.com/)

* **Python 3.12**
* **Discord Server:** With administrator permissions for initial bot setup.
* **Yahoo Fantasy API Authentication:** A free Yahoo Developer Network account is required.
* **`.env` file configuration:** You will need to fill out specific details in your `.env` file (explained in the Wiki).

### Basic Installation & Run:

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/vrabit/fantasybot.git](https://github.com/vrabit/fantasybot.git)
    cd fantasybot
    ```
2.  **Install dependencies using `uv` (recommended):**
    ```bash
    uv sync
    ```
    *Note: If `uv` is not available, you can use `pip install -r requirements.txt` after creating a virtual environment.*
3.  **Fill out your `.env` files:** (Refer to the Wiki for detailed instructions.)
4.  **Run the bot:**
    ```bash
    uv run main.py
    ```

---

### Initial Discord Setup (Commands):

Once running, interact with the bot in your Discord server to enable features:

* `/set_news`: Designates a channel for Rotowire news updates.
* `/set_transactions_channel`: Sets a channel for automatic fantasy league transaction posts.
* `/set_slap_channel`: Activates slap challenges and assigns a channel for results (requires wagers to be enabled).
* `/enable_wagers`: Enables the wager system and manages the token vault.

### 📚 Full Setup Guide & Commands

For detailed, step-by-step installation instructions (including Discord and Yahoo API setup with images), troubleshooting, and a complete list of all available commands, please visit our comprehensive Wiki:

👉 [**FantasyBot Wiki - Setup Guide**](https://github.com/vrabit/fantasybot/wiki) 👈

---
## 📸 In Action

See FantasyBot's features come to life! (Replace these with your actual screenshots/GIFs)

* **Live Matchup Scores:**
    [Screenshot/GIF showing a command like `/matchups` and the bot's rich embed response with current fantasy team points]

* **Interactive Wager System:**
  
   ![place_wager](https://github.com/user-attachments/assets/89acdf25-7688-4b0e-9ef3-0f2b1a9ead1b)

* **Week Recap Visualizations:**

   ![week_recap](https://github.com/user-attachments/assets/b27d8910-0022-4632-a6cb-78e3f1f9c1a8)


* **Season Recap Visualizations:**

   ![season_recap](https://github.com/user-attachments/assets/bca73316-1475-486f-a914-731092e9d6fc)


* **Trade Evaluation Chart:**
    [Screenshot/GIF showing the bar chart generated by `/trade_evaluate`]

---

## 💻 Built With

* **Python**
* [`discord.py`](https://github.com/Rapptz/discord.py) (for Discord interaction)
* [`YFPY`](https://github.com/uberfastman/yfpy) - Yahoo Fantasy Sports API Wrapper by Wren J. R. (uberfastman)
* [`uv`](https://github.com/astral-sh/uv) (dependency management and project runner)
* **Yahoo Fantasy Sports API**
* **FantasyCalc API**
* **Rotowire RSS Feed**
* **Seaborn** (for data visualization)

---

   ```
