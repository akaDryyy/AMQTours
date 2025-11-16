import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.tierMaker import TierMaker

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    tiermaker = TierMaker(
        directory=DIRECTORY, 
        sheetName="ngm stats", 
        tabStats=1315204448, 
        tabIDs=220350629, 
        tabEloStorage=716533894, 
        tabEloStorageCell='A10', 
        grWeight=0.35, 
        monthWindow=2, 
        maxFallbackWindow=6, 
        pastTours=10, 
        activeTours=20, 
        chosenYear=2025
    )
    tiermaker.make_tiers(
        alpha=3.75,
        midpoint=0.33,
        minRating=0,
        maxRating=25,
        ranksSpread=True
    )

if __name__ == '__main__':
    main()