import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.solver import Solver

def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    solver = Solver(
        directory=DIRECTORY, 
        maxSolutions=1
    )
    solver.solve(
        tourType="watched-in",
        isAutorank=True
    )

if __name__ == '__main__':
    main()