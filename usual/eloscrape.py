import ssl
import sys
import json
import math
from collections import deque

import certifi
import asyncio
import aiohttp 
import trueskill
import dateutil.parser as dp

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

import gspread, os
StoreElos=716533894
DIRECTORY = os.path.dirname(os.path.dirname(__file__))
alises_path = os.path.abspath(os.path.join(os.pardir, "aliases.txt"))
PROXY_SERVER = '' # get from tsui if necessary
TEAMSIZE = 4

trueskill.setup(
    mu=12, # mean rating 
    sigma=1.75, # initial uncertainty of a new player's rating -- recommended to be mu/3 in docs but redefined below since most people are relatively well rated to start (?)
    beta=7, # rating difference at which the higher-rated player has a ~76% chance of winning // initial 2
    tau=0.09, # change this to increase/decrease how much a regular player's rating is likely to swing // initial 0.04
    draw_probability=0.04, # based on jan-jul 2024 results 
    backend='mpmath'
    )

try:
    with open('historical_tourcount.json', 'r', encoding='utf-8') as f:
        HISTORICAL_TOURCOUNT = json.load(f)
except:
    HISTORICAL_TOURCOUNT = {}

tzd = {}

def init_timezones():
    tz_str = '''-12 Y
    -11 X NUT SST
    -10 W CKT HAST HST TAHT TKT
    -9 V AKST GAMT GIT HADT HNY
    -8 U AKDT CIST HAY HNP PST PT
    -7 T HAP HNR MST PDT
    -6 S CST EAST GALT HAR HNC MDT
    -5 R CDT COT EASST ECT EST ET HAC HNE PET
    -4 Q AST BOT CLT COST EDT FKT GYT HAE HNA PYT
    -3 P ADT ART BRT CLST FKST GFT HAA PMST PYST SRT UYT WGT
    -2 O BRST FNT PMDT UYST WGST
    -1 N AZOT CVT EGT IST
    0 Z EGST GMT UTC WET WT
    1 A CET DFT WAT WEDT WEST
    2 B CAT CEDT CEST EET SAST WAST
    3 C EAT EEDT EEST IDT MSK
    4 D AMT AZT GET GST KUYT MSD MUT RET SAMT SCT
    5 E AMST AQTT AZST HMT MAWT MVT PKT TFT TJT TMT UZT YEKT
    6 F ALMT BIOT BTT IOT KGT NOVT OMST YEKST
    7 G CXT DAVT HOVT ICT KRAT NOVST OMSST THA WIB
    8 H ACT AWST BDT BNT CAST HKT IRKT KRAST MYT PHT SGT ULAT WITA WST
    9 I AWDT IRKST JST KST PWT TLT WDT WIT YAKT
    10 K AEST ChST PGT VLAT YAKST YAPT
    11 L AEDT LHDT MAGT NCT PONT SBT VLAST VUT
    12 M ANAST ANAT FJT GILT MAGST MHT NZST PETST PETT TVT WFT
    13 FJST NZDT
    11.5 NFT
    10.5 ACDT LHST
    9.5 ACST
    6.5 CCT MMT
    5.75 NPT
    5.5 SLT
    4.5 AFT IRDT
    3.5 IRST
    -2.5 HAT NDT
    -3.5 HNT NST NT
    -4.5 HLV VET
    -9.5 MART MIT'''

    global tzd
    for tz_descr in map(str.split, tz_str.split('\n')):
        tz_offset = int(float(tz_descr[0]) * 3600)
        for tz_code in tz_descr[1:]:
            tzd[tz_code] = tz_offset

def start_time(tag):
    return tag.name == 'div' and tag.has_attr('class') and 'start-time' in tag['class']

def get_players(teamstr, elos, aliases, teamid):
    player_strs = teamstr.rstrip(')').split(') ')
    players = {}
    rounds_played = {
        teamid: {}
    }
    for player_str in player_strs:
        if '(' not in player_str:
            continue
        player, rank = player_str.split(' (')
        player = player.strip().lower()
        if '[' in player:
            player, rounds_played_str = player.split(' [')
            if player not in elos and player in aliases:
                player = aliases[player]
            rounds_played[teamid][player] = json.loads('[' + rounds_played_str)
        if player in aliases:
            player = aliases[player]
        if player in elos:
            players[player] = elos[player]
        else:
            players[player] = trueskill.Rating(mu=float(rank))
            
    return players, rounds_played

def handle_subs(team, rounds_played, round, teamid):
    if len(team) == TEAMSIZE:
        return team

    new_team = team.copy()
    for player in team.keys():
        if player in rounds_played[teamid] and round not in rounds_played[teamid][player]:
            print(f'deleting {player} in round {round}')
            del new_team[player]
    return new_team

async def parse_challonge_html(text):
    match_info_str = text.split("['TournamentStore'] = ")[1].split("; window._initialStoreState['ThemeStore'] = ")[0]
    match_info = json.loads(match_info_str)
    
    search = BeautifulSoup(text, 'lxml')
    time_str = search.find(start_time).string.strip()
    match_info['time'] = dp.parse(time_str, tzinfos=tzd)
    
    return match_info

async def get_challonge_info(session, url):
    tour_id = url.rstrip('/').split('/')[-1]
    try:
        with open(f'htmls/{tour_id}.html', 'r', encoding='utf-8') as f:
            text = f.read()
        match_info = await parse_challonge_html(text)
    except:
        print(f'cached html for {tour_id} not found, querying challonge...')
        resp = await session.get(url)
        text = resp.text
        with open(f'htmls/{tour_id}.html', 'w', encoding='utf-8') as f:
            f.write(text)
        match_info = await parse_challonge_html(text)
    
    match_info['tour_id'] = tour_id
    return match_info

async def main():
    init_timezones()

    aliases = {}
    with open(alises_path, 'r', encoding='utf-8') as f:
        # tab-separated list of aliases, where every line has all names of one player 
        # first of each line should be the main name (current bot name)
        for line in f:
            alias_list = line.split('\t')
            main_name = alias_list[0].strip().lower()
            for alias in alias_list:
                aliases[alias.strip().lower()] = main_name

    tourlist = []
    with open('tourlist.txt', 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url not in tourlist:
                tourlist.append(url)
    
    # comment this out if tsui is asleep
    # only use if having issues w/ curl-cffi
    # tourlist = [PROXY_SERVER + tour for tour in tourlist]
    elos = {}
    
    async with AsyncSession(impersonate='chrome123', max_clients=2) as session:
        try:
            challonges = await asyncio.gather(*[get_challonge_info(session, url) for url in tourlist])
            challonges.sort(key=lambda tour:tour['time'].timestamp())
        except IndexError:
            input('matches not processed, need to replace cookies, press enter to close')
            sys.exit(1)
    
    match_count = 0
    draw_count = 0
    elo_history_list = []
    for tour in challonges:
        teams = {}
        rounds_played = {}
        elo_history = {
            'tour_id': tour['tour_id'],
            'time': tour['time'].isoformat(sep=' '),
            'results': {},
            'teams': {},
            'players': {}
        }
        rounds = tour['matches_by_round']
        for round_info in rounds.values():
            for match in round_info:
                match_count += 1
                team1_id = match['player1']['id']
                team2_id = match['player2']['id']
                
                # add teams to tour 
                if team1_id not in teams:
                    team1, team1_rounds = get_players(match['player1']['display_name'], elos, aliases, team1_id)
                    teams[team1_id] = team1
                    rounds_played.update(team1_rounds)
                    teamstr = ''
                    team_initial_rating = 0
                    for player, rating in team1.items(): 
                        elo_history['players'][player] = rating.mu
                        if player in team1_rounds and 1 not in team1_rounds[player]:
                            continue
                        teamstr += f'{player} ({rating.mu:.2f}) '
                        team_initial_rating += rating.mu 
                    teamstr += f'= {team_initial_rating:.2f}'
                    elo_history['results'][team1_id] = {
                        'teamstr': teamstr,
                        'win': 0,
                        'loss': 0,
                        'draw': 0
                        }
                if team2_id not in teams:
                    team2, team2_rounds = get_players(match['player2']['display_name'], elos, aliases, team2_id)
                    teams[team2_id] = team2
                    rounds_played.update(team2_rounds)
                    teamstr = ''
                    team_initial_rating = 0
                    for player, rating in team2.items(): 
                        elo_history['players'][player] = rating.mu
                        if player in team2_rounds and 1 not in team2_rounds[player]:
                            continue
                        teamstr += f'{player} ({rating.mu:.2f}) '
                        team_initial_rating += rating.mu 
                    teamstr += f'= {team_initial_rating:.2f}'
                    elo_history['results'][team2_id] = {
                        'teamstr': teamstr,
                        'win': 0,
                        'loss': 0,
                        'draw': 0
                        }
                
                # calc rating changes 
                if not match['winner_id']:
                    draw_count += 1
                    team1 = handle_subs(teams[team1_id], rounds_played, match['round'], team1_id)
                    team2 = handle_subs(teams[team2_id], rounds_played, match['round'], team2_id)
                    new_ratings = trueskill.rate([team1, team2], ranks=[0,0])
                    teams[team1_id].update(new_ratings[0])
                    teams[team2_id].update(new_ratings[1])
                    elo_history['results'][team1_id]['draw'] += 1
                    elo_history['results'][team2_id]['draw'] += 1
                else:
                    winner_id = match['winner_id']
                    loser_id = match['loser_id']
                    winner_team = handle_subs(teams[winner_id], rounds_played, match['round'], winner_id)
                    loser_team = handle_subs(teams[loser_id], rounds_played, match['round'], loser_id)
                    new_ratings = trueskill.rate([winner_team, loser_team])
                    teams[winner_id].update(new_ratings[0])
                    teams[loser_id].update(new_ratings[1])
                    elo_history['results'][winner_id]['win'] += 1
                    elo_history['results'][loser_id]['loss'] += 1
                    
        elo_history['player'] = {}
        for team_id, team in teams.items():
            team_dict = elo_history['results'][team_id]
            teamstr = team_dict['teamstr']
            elo_history['teams'][teamstr] = f"{team_dict['win']}W {team_dict['loss']}L {team_dict['draw']}D"
            for player, rating in team.items():
                elo_history['player'][player] = f"initial elo: {elo_history['players'][player]:.3f}, new elo: {rating.mu:.3f}, rating change: {rating.mu - elo_history['players'][player]:.3f}"
            elos.update(team)
        del elo_history['results']
        del elo_history['players']
        elo_history_list.append(elo_history)
    
    print(rounds_played)
    
    with open('elos.json', 'w', encoding='utf-8') as f:
        elos_print = {player: round(rating.mu, 3) for player, rating in sorted(elos.items(), key=lambda elo: elo[1], reverse=True)}
        json.dump(elos_print, f, indent='\t')
    
    with open('elo_history.json', 'w', encoding='utf-8') as f:
        json.dump(elo_history_list, f, indent='\t')
        
    with open('elo_history_latest.json', 'w', encoding='utf-8') as f:
        json.dump(elo_history_list[-1], f, indent='\t')
    
    tierlist = {}
    for player, rating in elos_print.items():
        rating_int = int(round(rating))
        if rating_int not in tierlist:
            tierlist[rating_int] = [player]
        else:
            tierlist[rating_int].append(player)
    
    with open('elo_adjusted_tl.txt', 'w', encoding='utf-8') as f:
        tiers = sorted(list(tierlist.keys()), reverse=True)
        for tier in tiers:
            f.write(f'{tier}: {", ".join(tierlist[tier])}\n')
    
    with open('elo_adjusted_tl_finegrained.txt', 'w', encoding='utf-8') as f:
        tiers = sorted(list(tierlist.keys()), reverse=True)
        for tier in tiers:
            f.write(f'{tier}: {", ".join([f"{player} ({elos_print[player]})" for player in tierlist[tier]])}\n')

    gc = gspread.oauth(
        credentials_filename=DIRECTORY + '/credentials/credentials.json',
        authorized_user_filename=DIRECTORY + '/credentials/authorized_user.json'
    )
    sheet = gc.open('ngm stats')
    wks = sheet.get_worksheet_by_id(StoreElos)

    row = 0
    with open('./elos.json') as f:
        data = f.read()
        wks.update_acell('A1', data)
        
if __name__ == '__main__':
    asyncio.run(main())
