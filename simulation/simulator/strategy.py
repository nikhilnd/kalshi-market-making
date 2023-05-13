from state import TradingState
import dateparser 
from scipy.stats import cauchy 

POSITION_LIMIT = 40

class Strategy(): 

    def __init__(self, 
                 state: TradingState, 
                 min: int,
                 max: int,
                 EOD: int) -> None:
        self.state = state
        # Hardcoded constants
        self.EOD = EOD
        self.UPPER = max
        self.LOWER = min 
        self.x0 = 0 
        self.gamma = 0.000005

    def kalshiUpdate(self) -> None: 
        orderbook = self.state.getOrderbook()
        if len(orderbook["bids"]) == 0 or len(orderbook["asks"]) == 0:
            return

        # Convert self.state.time to unix timestamp
        curr_time = dateparser.parse(self.state.time)
        offset = self.EOD - curr_time.timestamp()
        curr_gamma = self.gamma*(offset)**(3/5)
        if offset <= 0 or curr_gamma == 0: 
            return 
        try: 
            p = cauchy.cdf((self.UPPER-self.state.sp_price)/self.state.sp_price, self.x0, curr_gamma) - cauchy.cdf((self.LOWER-self.state.sp_price)/self.state.sp_price, self.x0, curr_gamma)

            bid = round(p * 100) - 1
            ask = round(p * 100) + 1

            bid_vol = min(10, POSITION_LIMIT - self.state.position)
            ask_vol = min(10, POSITION_LIMIT + self.state.position)

            if self.state.position > 0:
                bid -= round(self.state.position / 10)
                ask -= round(self.state.position / 10)
            elif self.state.position < 0:
                bid += round(-self.state.position / 10)
                ask += round(-self.state.position / 10)

            best_bid = max(orderbook["bids"])
            best_ask = min(orderbook["asks"])

            self.state.insertOrder("B", bid, bid_vol)
            self.state.insertOrder("A", ask, ask_vol)
        except Exception as e: 
            pass
        
    def spUpdate(self) -> None: 
        orderbook = self.state.getOrderbook()
        if len(orderbook["bids"]) == 0 or len(orderbook["asks"]) == 0:
            return

        # Convert self.state.time to unix timestamp
        curr_time = dateparser.parse(self.state.time)
        offset = self.EOD - curr_time.timestamp()
        curr_gamma = self.gamma*(offset)**(3/5)
        if offset <= 0 or curr_gamma == 0: 
            return 
        try: 
            p = cauchy.cdf((self.UPPER-self.state.sp_price)/self.state.sp_price, self.x0, curr_gamma) - cauchy.cdf((self.LOWER-self.state.sp_price)/self.state.sp_price, self.x0, curr_gamma)

            bid = round(p * 100) - 1
            ask = round(p * 100) + 1

            bid_vol = min(10, POSITION_LIMIT - self.state.position)
            ask_vol = min(10, POSITION_LIMIT + self.state.position)

            if self.state.position > 0:
                bid -= round(self.state.position / 10)
                ask -= round(self.state.position / 10)
            elif self.state.position < 0:
                bid += round(-self.state.position / 10)
                ask += round(-self.state.position / 10)

            best_bid = max(orderbook["bids"])
            best_ask = min(orderbook["asks"])

            if bid >= best_ask and self.state.position > -20: 
                self.state.insertOrder("B", best_ask - 1, bid_vol)
            else: 
               self.state.insertOrder("B", bid, bid_vol)

            if ask <= best_bid and self.state.position < 20:
                self.state.insertOrder("A", best_bid + 1, ask_vol)
            else:
                self.state.insertOrder("A", ask, ask_vol)

        except Exception as e: 
            pass