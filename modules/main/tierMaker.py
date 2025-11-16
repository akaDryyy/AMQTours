import pandas as pd
import os
import json
import csv
import shutil
import argparse
from collections import defaultdict

from modules.support.cleanData import *
from modules.support.readCredentials import readCredentials
from modules.support.trim import trim
from modules.support.computeRanks import *
from modules.support.changelogMVPs import *
from modules.support.reset import reset_ranks
from modules.support.saveElos import saveElos

class TierMaker:
    def __init__(
            self, 
            directory, 
            sheetName, 
            tabStats, 
            tabIDs, 
            tabEloStorage, 
            tabEloStorageCell, 
            grWeight, 
            monthWindow, 
            maxFallbackWindow, 
            pastTours, 
            activeTours, 
            chosenYear
        ):
        """
        Tier Maker class

        Parameters:
            - directory = Directory where the file you are calling from resides
            - sheetName = Name of the spreadsheet
            - tabStats = GID of the stats tab
            - tabIDs = GID of the IDs tab
            - tabEloStorage = GID of the Elo Storage tab
            - tabEloStorageCell = Cell where to store elo
            - grWeight = Weight assigned to GR compared to UF
            - ufWeight = 1 - grWeight
            - monthWindow = Window from where stats will be drawn
            - maxFallbackWindow = Max window from where stats will be drawn if little data points available for one player
            - pastTours = Number of tours to consider before going into maxFallbackWindow
            - activeTours = Number of tours to consider per player. Usually coincides with pastTours
            - chosenYear = Year from which we start considering potentially usable data points
        """
        self.directory = directory
        self.sheetName = sheetName
        self.tabStats = tabStats
        self.tabIDs = tabIDs
        self.tabEloStorage = tabEloStorage
        self.tabEloStorageCell = tabEloStorageCell

        self.RANKS = os.path.join(self.directory, "ranks.txt")
        self.MVPS = os.path.join(self.directory, "mvps.txt")
        self.CHANGELOG = os.path.join(self.directory, "changelog.txt")
        self.ELOS = os.path.join(self.directory, "elos.json")
        self.TIERLIST = os.path.join(self.directory, "tierList.txt")
        self.IDTABLE = os.path.join(self.directory, "ids.csv")
        self.STATSTABLE = os.path.join(self.directory, "stats.csv")
        self.STATSTABLETMINUS1 = os.path.join(self.directory, "stats_tminus1.csv")
        self.CLEANEDSTATS = os.path.join(self.directory, "stats_clean.csv")
        self.CLEANEDSTATSYEAR = os.path.join(self.directory, "stats_clean_year.csv")

        self.grWeight = grWeight
        self.ufWeight = 1 - grWeight
        self.monthWindow = monthWindow
        self.maxFallbackWindow = maxFallbackWindow
        self.pastTours = pastTours
        self.activeTours = activeTours
        self.chosenYear = chosenYear

    def make_tiers(
            self,
            alpha,
            midpoint,
            minRating,
            maxRating,
            ranksSpread = False,
            hasExtraColumn = False
        ):
        parser = argparse.ArgumentParser(description="AMQ Tours")
        parser.add_argument('--keep', '-k', action='store_true',
                            help="Keep the current CSVs for stats, used for when doing changelogs one at the time after not running the script for multiple tours",
                            required=False)
        args = parser.parse_args()

        if not args.keep:
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

        clean_stats = clean_data(self.IDTABLE, self.STATSTABLE, self.CLEANEDSTATSYEAR, self.monthWindow, self.maxFallbackWindow, self.pastTours, self.activeTours, hasExtraColumn)
        clean_stats = clean_stats.sort_values(["Player ID", "Tournament Date"])
        clean_stats.to_csv(self.CLEANEDSTATS, index=False, encoding="utf-8")
        player_stats = clean_stats.groupby("Player ID").apply(trim, include_groups=False).reset_index()
        final_ranks = compute_ranks(player_stats, uf_max=(clean_stats["usefulness"].max()),
                                    alpha=alpha, midpoint=midpoint,
                                    GR_weight=self.grWeight, 
                                    min_score=minRating, max_score=maxRating, 
                                    spread=ranksSpread)
        ids = pd.read_csv(self.IDTABLE)
        ids = ids.drop_duplicates(subset='Player ID', keep='first')
        final_ranks = final_ranks.merge(ids[['Player ID', 'Player Name']], on='Player ID', how='left')
        new_order = ['Player ID', 'Player Name', 'elo', 'avg_gr', 'avg_uf', 'count', 'norm_gr', 'norm_uf', 'raw_score']
        final_ranks = final_ranks[new_order]
        final_ranks = final_ranks.sort_values(by='elo', ascending=False)
        print(final_ranks)
        rank_dict = dict(zip(final_ranks['Player Name'], final_ranks['elo'].round(3)))

        with open(self.ELOS, 'r') as f:
            old_elos = json.load(f)
            old_old_elos = old_elos

        with open(self.ELOS, 'w') as f:
            json.dump(rank_dict, f, indent=4)

        score_to_players = defaultdict(list)
        for player, score in rank_dict.items():
            score_to_players[round(score, 3)].append(player)

        with open(self.TIERLIST, "w") as f:
            for score in sorted(score_to_players.keys(), reverse=True):
                players = ", ".join(score_to_players[score])
                f.write(f"{score}: {players}\n")

        makeChangelog(rank_dict, old_elos, self.CHANGELOG)

        clean_stats_tnow = mini_clean(self.IDTABLE, self.STATSTABLE, hasExtraColumn)
        clean_stats_tminus1 = mini_clean(self.IDTABLE, self.STATSTABLETMINUS1, hasExtraColumn)
        last_tour = clean_stats_tnow.merge(clean_stats_tminus1, how='outer', indicator=True).query('_merge == "left_only"')
        if not last_tour.empty:
            player_stats_tour = last_tour.groupby("Player ID").apply(trim, include_groups=False).reset_index()
            last_tour_ranks = compute_ranks(player_stats_tour, uf_max=(clean_stats["usefulness"].max()),
                                            alpha=alpha, midpoint=midpoint,
                                            GR_weight=self.grWeight, 
                                            min_score=minRating, max_score=maxRating, 
                                            spread=ranksSpread)
            last_tour_ranks = last_tour_ranks.merge(ids[['Player ID', 'Player Name']], on='Player ID', how='left')
            last_tour_ranks = last_tour_ranks[new_order]
            last_tour_ranks = last_tour_ranks.sort_values(by='elo', ascending=False)
            last_tour_dict = dict(zip(last_tour_ranks['Player Name'], last_tour_ranks['elo'].round(3)))

            makeMVPs(last_tour_dict, old_old_elos, self.MVPS)

        # Latest tour will be the new most recent one afterwards
        shutil.copyfile(self.STATSTABLE, self.STATSTABLETMINUS1)

        reset_ranks(self.RANKS)

        if not args.keep:
            saveElos(self.directory, self.tabEloStorage, self.sheetName, self.tabEloStorageCell, self.ELOS)