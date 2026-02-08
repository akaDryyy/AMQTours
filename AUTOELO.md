# HOW IT WORKS

Stats based approach to determine a person rank.
**IMPORTANT** Once downloaded, move credentials folder inside each autoelo folder and run `setup.bat` if you do not have `pandas` already installed.

# TierMaker

- Downloads latest tour data and determines each player rating.
- Run it once before hosting a tour, so you are certain to be up to date.
- Run it after stats are made for a tour to obtain the `changelog.txt` and `mvps.txt` files.
    - Those files work with the difference between data, if your local data copy is not updated it will make generate the logs for all the played tours at once
    - Run `-k` or `--keep` to do not download automatically latest data and simply do a local diff.
    - This implies having to delete tours data from `stats.csv` and `stats_tminus1.csv`
    - For example, delete last tour from `stats.csv` and last two tours from `stats_tminus1.csv` to obtain the changelog and mvps of the last tour.

# NGMSolver

- Solver that works like the previous ones
- If there is a new player or someone without tour data in the fallback range, you will need to add them to `ranks.txt`. A warning should pop up when running the script in such cases.
- Results will go to `codes.txt` like previously
- **NEW PLAYERS OR NAME CHANGES**: At tour end, after stats are run, you should add any new player or name change to the ID Sheet, so that those stats can be properly tracked.

# STEP BY STEP GUIDE

1. Run `TierMaker.py` to update the elos to latest values
2. Add players to `players.txt`
3. Run `NGMSolver.py`, output will be found in `codes.txt`
    - If there is a new player, you will be prompted to add them to `ranks.txt`.
    - If there is a unrecognised alias, add them to `aliases.txt`. Use tabs, or copy and paste the space between two names in already existing examples.
4. When tour ends, run the stats
    - If there is a new player or a name change, add them with the correct ID inside NGMC Master v0.4's Reference Sheet
5. Run `TierMaker.py` again and post `changelog.txt` and `mvps.txt`

# GUIDELINES ON HOW TO ASSIGN A NEW RANK

Ranks differ from older ones, so the following guidelines will help assign one in case of a new or returning player.
This is only needed for their first tour, as their elo will be calculated automatically afterwards.
First, determine how many guesses the player is going to have, afterwards determine if they should be a high, low or mid inside the given amount of guesses.
Compare with other existing players inside `elos.json` to have guesstimate.

## Watched

≥28% = 5 guesses
18% - 28% = 4 guesses
12% - 18% = 3 guesses
6% - 12% = 2 guesses
<6% = 1 guess

## Random

≥28% = 4 guesses
19% - 28% = 3 guesses
8% - 19% = 2 guesses
<8% = 1 guess

FEEDBACK FOR THRESHOLDS ALWAYS APPRECIATED

# Step by step if you didn't update ranks before tour start:
- Run `TierMaker.py`. Your elos are now up to date with latest tour
- Delete latest tour from `stats.csv`
- Run `TierMaker.py -k`. The flag `-k` means to use local files. Your elos are now what they were before the latest tour
- Run `TierMaker.py` again without any flags. Your elos are now latest again but you have the correct delta for mvps