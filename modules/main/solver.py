import argparse, json, os, csv
import pandas as pd
from collections import defaultdict
from modules.support.readCredentials import readCredentials
from modules.support.getAliases import getAliases
from modules.support.getRanks import getRanks
from modules.support.cleanData import *
from modules.support.trim import *
from modules.support.LPProblem import LPProblem
from modules.support.computeRanks import *
from modules.support.getGuess import *
from modules.support.generateCodes import *
from modules.support.handleCodes import handleCodes
from modules.support.reset import reset_whitelist

class Solver:
    def __init__(
            self, 
            directory,
            maxSolutions,
            **kwargs
        ):
        """
        Solver class

        Parameters:
            - directory = Directory where the file you are calling from resides
            - maxSolutions = Number of solutions you want the solver to find
        kwargs for GR based thresholding:
            - sheetName = Name of the spreadsheet
            - tabStats = GID of the stats tab
            - tabIDs = GID of the IDs tab
            - monthWindow = Window from where stats will be drawn
            - maxFallbackWindow = Max window from where stats will be drawn if little data points available for one player
            - pastTours = Number of tours to consider before going into maxFallbackWindow
            - activeTours = Number of tours to consider per player. Usually coincides with pastTours
            Guess Thresholds: Percentages at which guess thresholds will change
                - oneGuess
                - twoGuess
                - threeGuess
        """
        self.directory = directory
        self.maxSolutions = maxSolutions
        for key, value in kwargs.items(): 
            setattr(self, key, value)

        self.BLACKLIST_PATH = os.path.abspath(os.path.join(self.directory, os.pardir, "blacklist.json"))
        self.WHITELIST_PATH = os.path.abspath(os.path.join(self.directory, os.pardir, "whitelist.json"))
        self.ALIASES_PATH = os.path.abspath(os.path.join(self.directory, os.pardir, "aliases.txt"))
        self.RANKS = os.path.join(self.directory, "ranks.txt")
        self.PLAYERS = os.path.join(self.directory, "players.txt")
        self.CODES = os.path.join(self.directory, "codes.txt")
        self.ELOS = os.path.join(self.directory, "elos.json")
        self.IDTABLE = os.path.join(self.directory, "ids.csv")
        self.STATSTABLE = os.path.join(self.directory, "stats.csv")
        self.CLEANEDSTATS = os.path.join(self.directory, "stats_clean.csv")
        self.CLEANEDSTATSYEAR = os.path.join(self.directory, "stats_clean_year.csv")
        self.TIERLIST = os.path.join(self.directory, "tierList.txt")
        self.FULLSTATS = os.path.join(self.directory, "stats_clean_full.csv")

        self.foundSolutions = []

        with open(self.BLACKLIST_PATH, "r") as f:
            self.blacklist = json.load(f)
        self.blacklist = [[a.lower(), b.lower()] for a, b in self.blacklist]
        with open(self.WHITELIST_PATH, "r") as f:
            self.whitelist = json.load(f)
        self.whitelist = [[a.lower(), b.lower()] for a, b in self.whitelist]
    
    def solve(
            self,
            tourType,
            grApproach = False,
            isAutorank = False,
            ranksSpread = False,
            isOld = False
        ):
        """
        Parameters:
            - tourType = usual / watched / op / ed / in
            - grApproach = Defaults to False. True if need to use grBased thresholds
            - isAutorank = Defaults to False. True if autorank
            - grWeight = Set only if autorank
            - ranksSpread = Defaults to False. True if need bigger spread between autoranks
            - isOld = Defaults to False. True if needs basic solving functionalities, like old solver which only had ranks file and not elo file
        """
        parser = argparse.ArgumentParser(description="AMQ Tours")
        parser.add_argument('--size', '-s',
                            help="Define the size of each team",
                            default=4,
                            required=False)
        if tourType == "usual":
            parser.add_argument('--mode', '-m', 
                                choices=['usual', 'quag'],
                                default="usual",
                                required=False,
                                help="Define the tour mode, currently usual or quag")
        elif tourType.startswith("watched"):
            parser.add_argument('--mode', '-m', 
                            choices=['30', '35', '40', '45', '50'],
                            default='40',
                            required=False,
                            help="Define the tour difficulty range")
        parser.add_argument('--thinktime', '-t',
                            help="Define how long should the script take to find solutions. Less think time might result in less team options provided.",
                            default=15000,
                            required=False)
        args = parser.parse_args()
        if args.size:
            team_size = int(args.size)
        try:
            if args.mode:
                gamemode = args.mode
        except AttributeError:
            pass
        if args.thinktime:
            thinkTime = args.thinktime

        self.tiers, self.tier_weights = get_tiers(tourType)

        if grApproach:
            gc = readCredentials(self.directory)

            sheet = gc.open(self.sheetName)
            wks = sheet.get_worksheet_by_id(self.tabStats)
            wks_ids = sheet.get_worksheet_by_id(self.tabIDs)

            rows = wks.get_all_values()
            with open(self.STATSTABLE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)

            rows_ids = wks_ids.get_all_values()
            with open(self.IDTABLE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows_ids)

            clean_stats, max_stats = clean_data(self.IDTABLE, self.STATSTABLE, self.CLEANEDSTATSYEAR, self.maxFallbackWindow, self.activeTours, tourType)
            clean_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
            clean_stats.to_csv(self.CLEANEDSTATS, index=False, encoding="utf-8")
            player_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
            max_stats.to_csv(self.FULLSTATS, index=False, encoding="utf-8")

        aliases = getAliases(self.ALIASES_PATH)
        
        players = {}
        if isAutorank:
            ranks, raw_ranks, post_ranks_fixup = getRanks(self.RANKS, self.ELOS, returnFixup=True)
            with open(self.PLAYERS, 'r') as file:
                for player in file.read().split(','):
                    player = player.strip().split(' (')[0]
                    player = player.lower()
                    player_key = player
                    if player_key in ranks:
                        new_player = {player: ranks[player_key]}
                        players.update(new_player)
                    # Check aliases
                    elif player_key in aliases:
                        main_name = aliases[player_key]
                        main_name = main_name.strip().lower()
                        if main_name in ranks:
                            players[player] = ranks[main_name]
                        else:
                            input(f"[WARN] Alias '{player}' maps to '{main_name}', but '{main_name}' not in ranks. Press Enter to continue.")
                    else:
                        # Not in current elo, check if new player or stats exist for them
                        alias_df = pd.read_csv(self.IDTABLE)
                        alias_df["Player Name"] = alias_df["Player Name"].str.strip().str.lower()
                        alias_to_id = dict(zip(alias_df["Player Name"], alias_df["Player ID"]))
                        if player_key in alias_to_id:
                            player_id = alias_to_id[player_key]
                        else:
                            player_id = None
                        # If player found, generate the elo
                        if player_id:
                            df = pd.read_csv(self.CLEANEDSTATSYEAR)
                            df = df[df['Player ID'] == player_id]
                            # Reset in case need to grab multiple IDs 
                            player_id = None
                            if not df.empty:
                                clean_fb = pd.read_csv(self.FULLSTATS)
                                normalization_spec = get_normalization_spec(clean_fb, tourType)
                                final_df = compute_ranks(clean_stats=df, full_stats=clean_fb, normalization_spec=normalization_spec,
                                                         tiers=self.tiers, tier_weights=self.tier_weights,
                                                         full=False)
                                rank_dict = dict(zip(final_df['PlayerName'], final_df['ELO'].round(3)))
                                ranks.update(rank_dict)
                                raw_ranks.update(rank_dict)
                                players[player] = ranks[list(rank_dict.keys())[0]]
                            else:
                                input(f"[WARN] Player '{player}' was found in ranks but has no data in the past months. Manually add to ranks.txt. Press Enter to exit.")
                                exit()
                        else:
                            input(f"[WARN] Player '{player}' not found in ranks or aliases. Manually add to ranks.txt. Press Enter to exit.")
                            exit()
        else:
            if isOld:
                ranks = getRanks(self.RANKS)
            else:
                ranks = getRanks(self.RANKS, self.ELOS)
            with open(self.PLAYERS, 'r') as file:
                for player in file.read().split(','):
                    player = player.strip().split(' (')[0]
                    player = player.lower()
                    player_key = player
                    if player_key in ranks:
                        new_player = {player: ranks[player_key]}
                        players.update(new_player)
                    # Check aliases
                    elif player_key in aliases:
                        main_name = aliases[player_key]
                        print(main_name)
    
                        if main_name in ranks:
                            players[player] = ranks[main_name]
                        else:
                            input(f"[WARN] Alias '{player}' maps to '{main_name}', but '{main_name}' not in ranks. Press Enter to exit.")
                            exit()
                    else:
                        input(f"[WARN] Player '{player}' not found in ranks or aliases. Press Enter to exit.")
                        exit()

        players = dict(sorted(((k.lower(), v) for k, v in players.items()), key=lambda x: x[1], reverse=True))
        players = list(players.items())

        if isAutorank:
            raw_ranks.update(post_ranks_fixup)
            raw_ranks = dict(sorted(raw_ranks.items(), key=lambda x: -x[1]))
            score_to_players = defaultdict(list)
            for player_to_append, score in raw_ranks.items():
                score_to_players[round(score, 3)].append(player_to_append)

            with open(self.ELOS, "w") as f:
                json.dump(raw_ranks, f, indent=4)
            with open(self.TIERLIST, "w") as f:
                for score in sorted(score_to_players.keys(), reverse=True):
                    string_players = ", ".join(score_to_players[score])
                    f.write(f"{score}: {string_players}\n")

        nums = [val for _, val in players]
        k = int(len(nums) / team_size)
        p_values = {p[0]: p[1] for p in players}

        self.foundSolutions = LPProblem(players, team_size, self.blacklist, self.whitelist, self.maxSolutions, thinkTime)

        # Automatic code generation
        CODE_HANDLERS = {
            "usual": {
                "normal":  {
                    False: (get_guess_usual,      generate_codes_usual),
                    True:  (get_guess_old_usual,  generate_codes_old_usual)
                },
                "gr": {
                    False: (get_guess_usual_gr,   generate_codes_usual_gr)
                }
            },
            "usual-house": {
                "normal": {
                    False: (get_guess_old_usual,  generate_codes_house_usual)
                }
            },
            "watched": {
                "normal": {
                    False: (get_guess_watched,     generate_codes_watched),
                    True:  (get_guess_old_watched, generate_codes_old_watched)
                },
                "gr": {
                    False: (get_guess_watched_gr,   generate_codes_watched_gr)
                }
            },
            "watched-in": {
                "normal": {
                    False: (get_guess_watched_in,  generate_codes_watched_in)
                },
                "gr": {
                    False: (get_guess_watched_gr,   generate_codes_watched_in_gr)
                }
            },
            "watched-cl": {
                "normal": {
                    False: (get_guess_watched_cl,  generate_codes_watched_cl)
                },
                "gr": {
                    False: (get_guess_watched_gr,   generate_codes_watched_cl_gr)
                }
            },
            "watched-5s": {
                "normal": {
                    False: (get_guess_watched_5s,  generate_codes_watched_5s)
                },
                "gr": {
                    False: (get_guess_watched_gr,   generate_codes_watched_5s_gr)
                }
            },
            "op": {
                "normal": {
                    False: (get_guess_op,     generate_codes_op),
                    True:  (get_guess_op_old, generate_codes_op_old)
                },
                "gr": {
                    False: (get_guess_usual_gr,   generate_codes_op_gr)
                }
            },
            "ed": {
                "normal": {
                    False: (get_guess_ed,     generate_codes_ed),
                    True:  (get_guess_ed_old, generate_codes_ed_old)
                },
                "gr": {
                    False: (get_guess_usual_gr,   generate_codes_ed_gr)
                }
            },
            "in": {
                "normal": {
                    False: (get_guess_in,     generate_codes_in),
                    True:  (get_guess_in_old, generate_codes_in_old)
                },
                "gr": {
                    False: (get_guess_usual_gr,   generate_codes_in_gr)
                }
            },
            "cl": {
                "normal": {
                    False: (get_guess_cl,     generate_codes_cl)
                },
                "gr": {
                    False: (get_guess_usual_gr,   generate_codes_cl_gr)
                }
            }
        }

        def get_handlers(tourType: str, isOld: bool, grApproach: bool):
            mode = "gr" if grApproach else "normal"
            try:
                return CODE_HANDLERS[tourType][mode][isOld]
            except KeyError:
                raise ValueError(f"No handler configured for tourType={tourType}, "
                                f"mode={mode}, isOld={isOld}")

        def process_code(
            self,
            tourType,
            isOld,
            grApproach,
            p_values,
            k,
            player_stats=None,
            gamemode=None
        ):

            get_guess, get_codes = get_handlers(tourType, isOld, grApproach)

            kwargs = {}
            if grApproach:
                if tourType.startswith("watched"):
                    kwargs = {
                        "player_stats": player_stats,
                        "idtable": self.IDTABLE,
                        "oneg": self.oneGuess,
                        "twog": self.twoGuess,
                        "threeg": self.threeGuess,
                        "fourg": self.fourGuess
                    }
                else:
                    kwargs = {
                        "player_stats": player_stats,
                        "idtable": self.IDTABLE,
                        "oneg": self.oneGuess,
                        "twog": self.twoGuess,
                        "threeg": self.threeGuess
                    }

            return handleCodes(
                foundSolutions=self.foundSolutions,
                p_values=p_values,
                k=k,
                get_guesses=get_guess,
                kwargs_guesses=kwargs or None,
                get_codes=get_codes,
                gamemode=gamemode,
                gr_based=grApproach
            )

        kwargs = {}
        if "player_stats" in locals():
            kwargs["player_stats"] = player_stats
        if "gamemode" in locals():
            kwargs["gamemode"] = gamemode
            
        final_code = process_code(
            self,
            tourType=tourType, 
            isOld=isOld, 
            grApproach=grApproach, 
            p_values=p_values, 
            k=k, 
            **kwargs
        )

        with open(self.CODES, "w", encoding="utf-8") as f:
            f.write(final_code)

        reset_whitelist(self.WHITELIST_PATH)

        _ = input("Finished making teams. Open `codes.txt` to find all the necessary. Press any key to continue...")