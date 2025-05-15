# Yahoo Fantasy Football Discord Bot

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)


## Features

- 📊 **Live League Stats**: Pulls team standings, matchup scores, and player info from Yahoo Fantasy Football.
- 📰 **NFL News Integration**: Delivers relevant player updates via Rotowire's RSS feed.
- 🤖 **Discord Slash Commands**:
- 🔗 **User Binding**: Maps Discord users to Yahoo usernames for personalized queries.


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
