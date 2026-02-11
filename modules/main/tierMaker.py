import pandas as pd
import os
import json
import csv
import shutil
import argparse
from collections import defaultdict

from modules.support.cleanData import *
from modules.support.readCredentials import readCredentials
from modules.support.trim import *
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
            maxFallbackWindow,
            activeTours
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
        self.FULLSTATS = os.path.join(self.directory, "stats_clean_full.csv")
        self.AVGSTATS = os.path.join(self.directory, "stats_prenormalized.csv")
        self.FINALSTATS = os.path.join(self.directory, "stats_postnormalized.csv")
        self.PREWRSTATS = os.path.join(self.directory, "stats_prewinrate.csv")

        self.maxFallbackWindow = maxFallbackWindow
        self.activeTours = activeTours

    def make_tiers(
            self,
            alpha,
            midpoint,
            minRating,
            maxRating,
            tourType
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

        self.tiers, self.tier_weights = get_tiers(tourType)

        clean_stats, full_stats = clean_data(self.IDTABLE, self.STATSTABLE, self.CLEANEDSTATSYEAR, self.maxFallbackWindow, self.activeTours, tourType)
        clean_stats = clean_stats.sort_values(["Player ID", "Timestamp"])
        clean_stats.to_csv(self.CLEANEDSTATS, index=False, encoding="utf-8")
        full_stats = full_stats.sort_values(["Player ID", "Timestamp"])
        full_stats.to_csv(self.FULLSTATS, index=False, encoding="utf-8")

        normalization_spec = get_normalization_spec(full_stats, tourType)

        final_ranks = compute_ranks(clean_stats, full_stats, normalization_spec, self.tiers, self.tier_weights,
                                    alpha, midpoint, minRating, maxRating, path=self.AVGSTATS, isWatched=tourType.startswith("watched"), wrpath=self.PREWRSTATS)
        print(final_ranks)
        final_ranks.to_csv(self.FINALSTATS, index=False, encoding="utf-8")
        rank_dict = dict(zip(final_ranks['PlayerName'], final_ranks['ELO'].round(3)))

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

        clean_stats_tnow = mini_clean(self.IDTABLE, self.STATSTABLE, tourType)
        clean_stats_tminus1 = mini_clean(self.IDTABLE, self.STATSTABLETMINUS1, tourType)
        last_tour = clean_stats_tnow.merge(clean_stats_tminus1, how='outer', indicator=True).query('_merge == "left_only"')
        if not last_tour.empty:
            last_tour_ranks = compute_ranks(last_tour, full_stats, normalization_spec, self.tiers, self.tier_weights,
                                            alpha, midpoint, minRating, maxRating, full=False, isWatched=tourType.startswith("watched"))
            last_tour_dict = dict(zip(last_tour_ranks['PlayerName'], last_tour_ranks['ELO']))

            makeMVPs(last_tour_dict, old_old_elos, self.MVPS)

        # Latest tour will be the new most recent one afterwards
        shutil.copyfile(self.STATSTABLE, self.STATSTABLETMINUS1)

        reset_ranks(self.RANKS)

        if not args.keep:
            saveElos(self.directory, self.tabEloStorage, self.sheetName, self.tabEloStorageCell, self.ELOS)

        _ = input("Finished updating ranks. Press any key to continue...")