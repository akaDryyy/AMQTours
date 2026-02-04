import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.tierMaker import TierMaker

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    tiermaker = TierMaker(
        directory=DIRECTORY, 
        sheetName="NGM Stats Export v2", 
        tabStats=591917504, 
        tabIDs=1903970832, 
        tabEloStorage=82254993, 
        tabEloStorageCell='A10',
        maxFallbackWindow=6,
        activeTours=10
    )
    tiermaker.make_tiers(
        alpha=3.75,
        midpoint=0.33,
        minRating=0,
        maxRating=25,
        tourType="op"
    )

if __name__ == '__main__':
    main()