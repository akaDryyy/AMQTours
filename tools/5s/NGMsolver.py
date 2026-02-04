import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.solver import Solver

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    solver = Solver(
        directory=DIRECTORY, 
<<<<<<< HEAD
        maxSolutions=1,
        sheetName="NGM Stats Export v2", 
        tabStats=676003100, 
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
        tourType="watched-5s",
        grApproach=True
=======
        maxSolutions=1
    )
    solver.solve(
        tourType="5s"
>>>>>>> e05c619 (trying to build an interface (not done))
    )

if __name__ == '__main__':
    main()