import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.tierMaker import TierMaker

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    tiermaker = TierMaker(
        directory=DIRECTORY, 
        sheetName="ngm stats", 
        tabStats=0, 
        tabIDs=220350629, 
        tabEloStorage=716533894, 
        tabEloStorageCell='A6', 
        grWeight=0.375, 
        monthWindow=2, 
        maxFallbackWindow=6, 
        pastTours=10, 
        activeTours=20, 
        chosenYear=2025
    )
    tiermaker.make_tiers(
        alpha=3.75,
        midpoint=0.3,
        minRating=-5,
        maxRating=30,
        ranksSpread=True,
        hasExtraColumn=True
    )

if __name__ == '__main__':
    main()