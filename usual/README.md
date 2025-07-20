# NGM ELO

ELO calculation + balance scripts for NGMC

## HOW TO USE

### eloscrape.py 

1. (FIRST TIME ONLY) install python if you hadn't already and `pip install -r requirements.txt`, or run the provided `setup.bat` file
2. put ALL tours that you want to count towards elo in `tourlist.txt`.
3. run the script 
4. if you get ssl errors run `eloscrape_insecure.py` instead

### NGMbalance_v3.5 

1. install python 
2. get the latest `elos.json` 
3. get `ranks.txt` (the script uses this for players w/o a rating yet) and fill `players.txt` with the players you want to balance 
4. run the script

### NGMbsolver.py

1. install python 
2. get the latest `elos.json` 
3. get `ranks.txt` (the script uses this for players w/o a rating yet) and fill `players.txt` with the players you want to balance 
4. run the script
- `-s 3` to change the team size to 3, or any desired number. Defaults to 4
- `-m quag` to change the code to quag. Defaults to usual

## USAGE NOTES

- challonge team names 
	- should be in the format exactly provided by the balance script 
	- i.e. `{PLAYER} ({RANK}) {PLAYER} ({RANK}) {PLAYER} ({RANK}) {PLAYER} ({RANK}) `
- sub handling 
	- if a player subs then note which rounds they played and the rounds they played in the tour and change their team name accordingly
	- e.g. `bop (19.79) LelPop [1, 2, 3] (10.09) MrWolf [4, 5] (11.44) Wuffles (7.79) Oshino_bu (5.45) = 43.12`
	- follow this format EXACTLY
	- after running the script ensure that the sub shows up in the latest elo history -- you may need to delete the html from your `htmls/` folder
- negative rated players 
	- balance algo can't handle negative players apparently 
	- I'll bugfix this at some point -- for now it just treats all negative players as 0

## FILE DESCRIPTIONS

- `eloscrape.py` -- (re)calculate ratings.
	- reads (input files):
		- `aliases.txt` -- tab-separated player aliases for merging. every alias on a line is assumed to be the same player, first name on each line  is the player's primary alias used for printing etc. NOT SUPPORTED: handling for different players using the same alias at some point. please flame anyone you see trying to do this.
		- `tourlist.txt` -- list of challonge IDs (URL ID, so the bit after the slash at the end, not API-internal ID) to use.
			- `htmls/{tour_id}.html` -- for each id in the above txt, this folder will get checked; attempts to query challonge only if no suitable saved html is found 
	- output:
		- `elos.json` -- simple sorted dict of playername: skill rating val. used for balancing
		- `elo_adjusted_tl.txt` -- integer tierlist in the same format as before. for legacy purposes (?)
		- `elo_adjusted_tl_finegrained.txt` -- as above except with the decimal elos also printed. probably not useful for anything tbh just use one of the above two files 
		- `elo_history.json` -- list of processed tours + results + how each player's elo was affected 
		- `elo_latest_history.json` -- ^ but only the last entry (for posting in #stuff)
	- usage notes:
		- for each player the initial elo value is the rating that appears on the challonge the player is first seen in, since there's no tierlist history saved anywhere 
		- if you want to adjust how much an individual tour affects player ratings change the values w/ notes at the top of the script. probably `tau` and `INITIAL_SIGMA` are the primary values of interest
- `NGMbalance_v3.5.py` -- balance with elos 
	- uses `elos.json` 
	- put player list in `players.txt` as usual 