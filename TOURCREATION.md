# Steps to create a tour

/tour_create [timer | size | info | ping] - Change timer, size (usually 16) and info
/tour_edit [timer | size | lfp | info] - Edit, used for timer extension, letting queue in with size +8 and lfp lock

When timer ends make teams:
/tour_players_list or copy the player list
Paste it into players.txt of the desired folder
Run NGMsolver.py
Find the results in codes.txt
Create the challonge:
- Name = Watched/Random/Your Choice
- Game = AMQ
- Format = RR + Participants play each other twice (4 teams), RR + play once (6 teams), Swiss (8+ teams)
Post Teams + Contents of codes.txt + Challonge

/tour_players_ping - Ping the players in tour, dictates the start of the stall timer

When the tour ends:
Post Winners + Screenshots
**Usual Only**: ELO
>Check that you have latest tourlist.txt and elos.json (grab from <#1266625479960563774> [elo stuff random thread])
>Append to tourlist.txt challonge link
>Run eloscrape.py (it will take a while for the first time)
>Post elo_history_latest.json to <#812164235421155328> [stuff channel]
>Post elos.json and tourlist.txt to <#1266625479960563774> [elo stuff random thread]

/tour_end - End the tour, final step