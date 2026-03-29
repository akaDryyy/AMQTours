from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.support.LPProblem import LPProblem
from modules.support.handleCodes import handleCodes
from modules.support.generateCodes import *
from models import Players, WhiteList, TourType, Challonge
from typing import Optional
from utils import get_guess_watched, get_guess_random, get_player_stats, get_blacklist, add_to_tourlist
from modules.main.eloscrape import EloScrape
from modules.main.tierMaker import TierMaker

app = FastAPI()

origins = ["http://127.0.0.1:5000", "http://localhost:5000"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.post("/solver")
def solver(people: Players, team_size: int, tourType: TourType, whitelist: Optional[WhiteList]):
    players = [(p.name, p.rating) for p in people.players]
    whitelist = [[team.player1, team.player2] for team in whitelist.teams]
    p_values = {p.name: p.rating for p in people.players}
    teams_number = int(len(players) / team_size)
    blacklist = get_blacklist()
    teams = LPProblem(players, team_size, blacklist, whitelist, max_solutions=1, think_time=15000)

    match tourType:
        case TourType.WATCHED:
            path = "watched_autoelo"
            player_stats, idtable = get_player_stats(path=path, tabStats=1719516221, tabIDs=1903970832, type="watched")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 6, "twog": 12, "threeg": 18, "fourg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_watched,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_watched_gr, gamemode="40", gr_based=True)
            
        case TourType.WATCHED_INS:
            path = "in_watched"
            player_stats, idtable = get_player_stats(path=path, tabStats=1177294729, tabIDs=1903970832, type="watched-in")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 6, "twog": 12, "threeg": 18, "fourg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_watched,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_watched_in_gr, gamemode="40", gr_based=True)
            
        case TourType.WATCHED_5S:
            path = "5s"
            player_stats, idtable = get_player_stats(path=path, tabStats=676003100, tabIDs=1903970832, type="watched-5s")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 6, "twog": 12, "threeg": 18, "fourg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_watched,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_watched_5s_gr, gamemode="no", gr_based=True)
            
        case TourType.RANDOM:
            path = "usual"
            player_stats, idtable = get_player_stats(path=path, tabStats=0, tabIDs=1903970832, type="usual")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 8, "twog": 19, "threeg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_random,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_usual_gr, gamemode="usual", gr_based=True)
            
        case TourType.RANDOM_15S:
            path = "usual"
            player_stats, idtable = get_player_stats(path=path, tabStats=0, tabIDs=1903970832, type="usual")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 8, "twog": 19, "threeg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_random,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_usual_gr, gamemode="quag", gr_based=True)
            
        case TourType.RANDOM_OP:
            path = "op_autoelo"
            player_stats, idtable = get_player_stats(path=path, tabStats=591917504, tabIDs=1903970832, type="op")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 8, "twog": 19, "threeg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_random,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_op_gr, gamemode=None, gr_based=True)
            
        case TourType.RANDOM_ED:
            path = "ed_autoelo"
            player_stats, idtable = get_player_stats(path=path, tabStats=601464032, tabIDs=1903970832, type="ed")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 8, "twog": 19, "threeg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_random,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_ed_gr, gamemode=None, gr_based=True)
            
        case TourType.RANDOM_INS:
            path = "in_autoelo"
            player_stats, idtable = get_player_stats(path=path, tabStats=2075065970, tabIDs=1903970832, type="in")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 8, "twog": 19, "threeg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_random,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_in_gr, gamemode=None, gr_based=True)
            
        case TourType.RANDOM_CL:
            path = "cl-usual"
            player_stats, idtable = get_player_stats(path=path, tabStats=1506914251, tabIDs=1903970832, type="cl")
            kwargs = {"player_stats": player_stats, "idtable": idtable, "oneg": 8, "twog": 19, "threeg": 28}
            finalcodes = handleCodes(foundSolutions=teams, p_values=p_values, k=teams_number, get_guesses=get_guess_random,
                kwargs_guesses=kwargs or None, get_codes=generate_codes_cl_gr, gamemode=None, gr_based=True)

    return finalcodes

@app.get("/tiermaker")
def tiermaker(tourType: TourType):
    """
    Watched 5s, Random, Watched 2+8 don't use tiermaker.
    """
    match tourType:
        case TourType.WATCHED:
            tiermaker = TierMaker(directory="watched_autoelo", sheetName="NGM Stats Export v2", tabStats=1719516221, 
                tabIDs=1903970832, tabEloStorage=82254993, tabEloStorageCell='A7',maxFallbackWindow=6,activeTours=10)
            tiermaker.make_tiers(alpha=3.75,midpoint=0.4,minRating=0,maxRating=25,tourType="watched",gui=True)
            return True
                
        case TourType.WATCHED_INS:
            tiermaker = TierMaker(directory="in_watched", sheetName="NGM Stats Export v2", tabStats=1177294729, 
                tabIDs=1903970832, tabEloStorage=82254993, tabEloStorageCell='A8',maxFallbackWindow=6,activeTours=10)
            tiermaker.make_tiers(alpha=3.75,midpoint=0.4,minRating=0,maxRating=25,tourType="watched-in",gui=True)
            return True
  
        case TourType.RANDOM_OP:
            tiermaker = TierMaker(directory="op_autoelo", sheetName="NGM Stats Export v2", tabStats=591917504, 
                tabIDs=1903970832, tabEloStorage=82254993, tabEloStorageCell='A10',maxFallbackWindow=6,activeTours=10)
            tiermaker.make_tiers(alpha=3.75,midpoint=0.33,minRating=0,maxRating=25,tourType="op",gui=True)
            return True

        case TourType.RANDOM_ED:
            tiermaker = TierMaker(directory="ed_autoelo", sheetName="NGM Stats Export v2", tabStats=601464032, 
                tabIDs=1903970832, tabEloStorage=82254993, tabEloStorageCell='A11',maxFallbackWindow=6,activeTours=10)
            tiermaker.make_tiers(alpha=3.75,midpoint=0.33,minRating=0,maxRating=25,tourType="ed",gui=True)
            return True
            
        case TourType.RANDOM_INS:
            tiermaker = TierMaker(directory="in_autoelo", sheetName="NGM Stats Export v2", tabStats=2075065970, 
                tabIDs=1903970832, tabEloStorage=82254993, tabEloStorageCell='A12', maxFallbackWindow=6, activeTours=10)
            tiermaker.make_tiers(alpha=3.75,midpoint=0.33,minRating=0,maxRating=25,tourType="in",gui=True)
            return True

        case TourType.RANDOM_CL:
            tiermaker = TierMaker(directory="cl-usual", sheetName="NGM Stats Export v2", tabStats=1506914251, 
                tabIDs=1903970832, tabEloStorage=82254993, tabEloStorageCell='A13',maxFallbackWindow=6,activeTours=10)
            tiermaker.make_tiers(alpha=3.75,midpoint=0.33,minRating=0,maxRating=25,tourType="cl",gui=True)
            return True

    return False

@app.post("/eloscrape")
async def eloscrape(tourType: TourType, challonge: Challonge):
    challonge_str = challonge.challonge
    match tourType:
        case TourType.WATCHED_5S:
            path = "5s"
            add_to_tourlist(tour=challonge_str, folder=path)
            eloscraper = EloScrape(directory=path, tabEloStorage=716533894, tabEloStorageCell="A3", sheetName="ngm stats", 
                mu=12, sigma=4, beta=7, tau=0.09, draw_probability=0.04)
            await eloscraper.eloscrape()
            return True
        
        case TourType.RANDOM:
            path = "usual"
            add_to_tourlist(tour=challonge_str, folder=path)
            eloscraper = EloScrape(directory=path, tabEloStorage=716533894, tabEloStorageCell="A1", sheetName="ngm stats", 
                mu=12, sigma=1.75, beta=7, tau=0.09, draw_probability=0.04)
            await eloscraper.eloscrape()
            return True
        
        case TourType.RANDOM_15S:
            path = "usual"
            add_to_tourlist(tour=challonge_str, folder=path)
            eloscraper = EloScrape(directory=path, tabEloStorage=716533894, tabEloStorageCell="A1", sheetName="ngm stats", 
                mu=12, sigma=1.75, beta=7, tau=0.09, draw_probability=0.04)
            await eloscraper.eloscrape()
            return True
        
    return False

#uvicorn api:app --reload