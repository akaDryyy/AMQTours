import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.solver import Solver

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    solver = Solver(
        directory=DIRECTORY, 
        maxSolutions=1,
        sheetName="ngm stats", 
        tabStats=0, 
        tabIDs=220350629, 
        thinkTime=15000,
        monthWindow=2, 
        maxFallbackWindow=6, 
        pastTours=10, 
        activeTours=10, 
        oneGuess=8, 
        twoGuess=19, 
        threeGuess=28
    )
    solver.solve(
        tourType="usual",
        grApproach=True
    )

if __name__ == '__main__':
    main()