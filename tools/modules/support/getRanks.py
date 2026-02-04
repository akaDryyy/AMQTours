import json

def getRanks(RANKS_PATH, ELOS_PATH=None, returnFixup=False):
    ranks = {}
    post_ranks_fixup = {}
    def process_rank(line):
        rank, rank_players = line.split(':', 2)
        rank = float(rank)
        rank_players = rank_players.strip().lower()
        for player in rank_players.split(','):
            if returnFixup:
                ranks[player.strip().lower()] = rank
                if player.strip() != '':
                    post_ranks_fixup[player.strip().lower()] = rank
            else:
                player_guesscount = player.rsplit(' [',2)
                playername = player_guesscount[0]
                ranks[playername.strip().lower()] = rank

    with open(RANKS_PATH, 'r') as file:
        for line in file.readlines():
            process_rank(line)

    if ELOS_PATH:
        with open(ELOS_PATH, 'r') as f:
            raw_ranks = json.load(f)
            cleaned_ranks = {k.strip().lower(): v for k, v in raw_ranks.items()}
            ranks.update(cleaned_ranks)

    ranks = {player: rank for player, rank in ranks.items()}

    if returnFixup:
        return ranks, raw_ranks, post_ranks_fixup
    else:
        return ranks