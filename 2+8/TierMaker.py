import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.tierMaker import TierMaker

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    tiermaker = TierMaker(
        directory=DIRECTORY, 
        sheetName="NGM Stats Export v2", 
        tabStats=0, #useless
        tabIDs=1903970832, #useless
        tabEloStorage=82254993, 
        tabEloStorageCell='A2', #important
        maxFallbackWindow=6, #useless
        activeTours=10 #useless
    )
    tiermaker.update_elos(tourlist_cell="C2") #important

if __name__ == '__main__':
    main()