import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.main.solver import Solver
from gooey import Gooey

@Gooey(show_success_modal=False)
def main():
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    solver = Solver(
        directory=DIRECTORY, 
        maxSolutions=5
    )
    solver.solve(
        tourType="ed",
        isOld=True
    )

if __name__ == '__main__':
    main()