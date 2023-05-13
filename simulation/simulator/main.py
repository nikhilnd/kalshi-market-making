from state import TradingState
from strategy import Strategy
from simulator import Simulator
import sys

if __name__ == "__main__":

    # Get index from command line
    index = int(sys.argv[1])
    if index < 0 or index > 2: 
        print("Invalid index, please enter 0 (Apr 10), 1 (Apr 13), or 2 (Apr 14))")
        exit()

    MIN = [4050, 4100, 4100] 
    MAX = [4100, 4150, 4150]
    EOD = [1681156800, 1681416000, 1681502400] 
    SOD = [1681133400, 1681392600, 1681479000]
    FILE = ["../data/apr-10-combined.csv", "../data/apr-13-combined.csv", "../data/apr-14-combined.csv"]

    state = TradingState(SOD[index])
    strategy = Strategy(state, MIN[index], MAX[index], EOD[index])
    simulator = Simulator(FILE[index], state, strategy)
    simulator.simulate()