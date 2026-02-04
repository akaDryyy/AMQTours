import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.solver import Solver

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    solver = Solver(
        directory=DIRECTORY, 
        maxSolutions=1,
        sheetName="NGM Stats Export v2", 
        tabStats=1719516221, 
        tabIDs=1903970832,
        thinkTime=15000,
        maxFallbackWindow=6, 
        activeTours=10, 
        oneGuess=6, 
        twoGuess=12, 
        threeGuess=18,
        fourGuess=28
    )
    solver.solve(
        tourType="watched",
        isAutorank=True,
        grApproach=True
    )

if __name__ == '__main__':
    main()