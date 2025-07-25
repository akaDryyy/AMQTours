# NGMbalance

Balance script for NGMC

## HOW TO USE

### NGMsolverwatched.py

1. get the latest `ranks.txt` 
2. fill `players.txt` with the players you want to balance. If you have team requests, fill `whitelist.json` in the above folder with the names of the players you want to put in the same team, follow the provided format, the name must match the one in `elos.json` or `aliases.txt`. If you want to team up 3 players simply do ['playerA', 'playerB'], ['playerB', 'playerC'].
3. run the script
- `-s 3` to change the team size to 3, or any desired number. Defaults to 4
- `-m 30` to change the code to 0-30. Defaults to 0-40, supports: 30, 35, 40, 45, 50
4. output will be put in `codes.txt` with already the correct lobby codes

## FILE DESCRIPTIONS

- `NGMsolverwatched.py` -- balance with ranks
  - uses `ranks.txt` 
  - put player list in `players.txt`
  - output will be put in `codes.txt` with already the correct lobby codes 