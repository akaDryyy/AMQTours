import sys, Tour, gspread, os
from datetime import date


DEBUG = "DEBUG" in os.environ and os.environ["DEBUG"].lower() == "true"

MAIN_SHEET_RANDOM=0
MAIN_SHEET_WATCHED=599282945
SHEET_PLAYER_IDS=220350629
SHEET_EXTRA_STATS=1324663165
MAIN_SHEET_SPEED=750525899
MAIN_SHEET_SAKU=987991878
MAIN_SHEET_OTHER=97265097
MAIN_SHEET_OPS=1315204448
MAIN_SHEET_EDS=1610602702
MAIN_SHEET_INS=560474782
MAIN_SHEET_5S=1745619597
MAIN_SHEET_WATCHED_INS=518118972


# 🐶
dog_weight = [
    1,      # 1/8
    9/14,   # 2/8
    17/42,  # 3/8
    1/4,    # 4/8
    3/20,   # 5/8
    1/12,   # 6/8
    1/28,   # 7/8
    0       # 8/8
]

txtvar = """=== NGMC Stats Calculator ===
[1]: Random FL
[2]: Watched FL
[3]: Watched INs
[4]: Watched FL 2+8s
[5]: Watched FL 5s
[6]: Watched FL Saku Elo
[7]: Random OPs
[8]: Random EDs
[9]: Random INs
[10]: Other Random
[11]: Other Watched
"""

print(txtvar)
gamemode = input("Select game mode [#]:")
match gamemode:
    case "1":
        gamemode = "Random"
        is_list = False
    case "2":
        gamemode = "Watched"
        is_list = True
    case "3":
        gamemode = "Watched INs"
        is_list = True
    case "4":
        gamemode = "Watched 2+8s"
        is_list = True
    case "5":
        gamemode = "Watched 5s"
        is_list = True
    case '6':
        gamemode = "Saku Elo"
        is_list = True
    case "7":
        gamemode = "Random OPs"
        is_list = False
    case "8":
        gamemode = "Random EDs"
        is_list = False
    case "9":
        gamemode = "Random INs"
        is_list = False
    case "10":
        gamemode = "Other Random"
        is_list = False
    case "11":
        gamemode = "Other Watched"
        is_list = True


DIRECTORY = os.path.dirname(__file__)
gc = gspread.oauth(
        credentials_filename=DIRECTORY + '/credentials/credentials.json',
        authorized_user_filename=DIRECTORY + '/credentials/authorized_user.json'
    )

def convert_to_dict(a):
    new_dict = {}
    for i in a:
        new_dict[i[0]] = i[1]
    return new_dict
    
def s(e): #will always be e[1] after ranks get phased out
    if is_list:
        return e[1]
    return e[2]


def sort_incomplete(e): #will always be e[2] after ranks get phased out
    if is_list:
        return e[2]
    return e[3]

avg_team = float(input("Enter the average team rank: "))

def post_to_sheet(tour):
    sheet = gc.open('ngm stats')
    match gamemode:
        case "Random":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_RANDOM)
        case "Watched":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_WATCHED)
        case "Watched INs":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_WATCHED_INS)
        case "Watched 2+8s":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_SPEED)
        case "Watched 5s":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_5S)
        case "Saku Elo":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_SAKU)
        case "Random OPs":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_OPS)
        case "Random EDs":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_EDS)
        case "Random INs":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_INS)
        case "Other Watched" | "Other Random":
            wks = sheet.get_worksheet_by_id(MAIN_SHEET_OTHER)
    sheet_size = len(wks.get_all_values())
    extra_stats_sheet = sheet.get_worksheet_by_id(SHEET_EXTRA_STATS)
    ids_dict = convert_to_dict(sheet.get_worksheet_by_id(SHEET_PLAYER_IDS).get_all_values())
    full_stats = []
    incomplete_stats = []

    for player in tour.players:
        op_rate, ed_rate, in_rate, rigs_missed, offlist_rate = 0, 0, 0, 0, 0
        guess_rate = round((sum(player.correct_songs) / sum(player.total_songs)) * 100, 3)
        avg_diff = round(player.total_diff / sum(player.correct_songs), 3)
        erigs = player.dog[0]
        dog = round(sum([player.dog[i]*(i+1) for i in range(8)]) / sum(player.correct_songs), 3)
        whats_up_dog = round((avg_team * 2 * sum([player.dog[i]* dog_weight[i] for i in range(8)])) / sum(player.total_songs), 3)
        if player.total_songs[0]:
            op_rate = round((player.correct_songs[0] / player.total_songs[0]) * 100, 3)
        if player.total_songs[1]:
            ed_rate = round((player.correct_songs[1] / player.total_songs[1]) * 100, 3)
        if player.total_songs[2]:
            in_rate = round((player.correct_songs[2] / player.total_songs[2]) * 100, 3)
        player_data = None
        if is_list:
            match gamemode:
                case "Other Watched":
                    rigs_missed = player.rigs - player.rigs_hit
                    offlist_rate = round(((sum(player.correct_songs) - player.rigs_hit) / (sum(player.total_songs) - player.rigs)), 3)
                    player_data = [player.name, guess_rate, whats_up_dog, avg_diff, erigs, dog, op_rate, ed_rate, in_rate, player.rigs, player.rigs_hit, sum(player.correct_songs), sum(player.total_songs), rigs_missed, offlist_rate]
                case _:
                    player_data = [player.name, guess_rate, whats_up_dog, avg_diff, erigs, dog, op_rate, ed_rate, in_rate, player.rigs, player.rigs_hit, sum(player.correct_songs), sum(player.total_songs)]
        else: #ranks replaced by a ? as preparation for phasing it out
            player_data = ["?", player.name, guess_rate, whats_up_dog, avg_diff, erigs, dog, op_rate, ed_rate, in_rate]

        if player.rounds_played < 5:
            player_data.insert(0, f"{player.rounds_played} games")
            incomplete_stats.append(player_data)
        else:
            full_stats.append(player_data)

    full_stats.sort(reverse=True, key=s)
    full_stats.insert(0, [str(date.today())])

    if not DEBUG:
        match gamemode:
            case "Other Watched":
                full_stats.insert(0, ["player name", "guess rate", "usefulness", "avg diff", "erigs", "avg /8 correct", "OP guess rate", "ED guess rate", "IN guess rate", "rigs", "rigs hit", "correct count", "song count", "Rigs missed", "Offlist GR"])
            case "Other Random":
                full_stats.insert(0, ["?", "player name", "guess rate", "usefulness", "avg diff", "erigs", "avg /8 correct", "OP guess rate", "ED guess rate", "IN guess rate"])
        wks.update(values=full_stats, range_name='A'+str(sheet_size + 2))
    else:
        for row in full_stats:
            print(" ".join([str(e) for e in row]))
    
    if len(incomplete_stats) > 0:
        print("Check the 'Extra Stats' sheet")
        incomplete_stats.sort(reverse=True, key=sort_incomplete)
        # Pad with empty rows to clear the rest
        while len(incomplete_stats) < 10:
            incomplete_stats.append([""] * len(incomplete_stats[0]))
        if is_list:
            extra_stats_sheet.update(values=incomplete_stats, range_name="A4")
        else:
            incomplete_stats.insert(0, ["Games Played","?","player name", "guess rate", "usefulness", "avg diff", "erigs", "avg /8 correct", "OP guess rate", "ED guess rate", "IN guess rate"])
            extra_stats_sheet.update(values=incomplete_stats, range_name="A18")
                       
    if len(tour.top_songs):
        print(f"\nTop {len(tour.top_songs)} played songs")
        for [song, play_count] in tour.top_songs:
            print(f"{song} - {play_count}")
    
    print(f"{wks.url}?range={sheet_size + 2}:{sheet_size + 2}")

def main():
    post_to_sheet(Tour.Tour(debug=DEBUG))
    _ = input('\npress enter to close')

if __name__ == "__main__":
    main()
