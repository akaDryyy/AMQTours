import sys, os
try:
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
except NameError:
    DIRECTORY = os.getcwd() 
PROJECT_ROOT = os.path.abspath(os.path.join(DIRECTORY, "..")) 
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from modules.main.solver import Solver

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    solver = Solver(
        directory=DIRECTORY, 
        maxSolutions=1,
        sheetName="NGM Stats Export v2", 
        tabStats=0, 
        tabIDs=1903970832, 
        thinkTime=15000,
        maxFallbackWindow=6, 
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