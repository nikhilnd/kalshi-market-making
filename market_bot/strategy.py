import asyncio
from ordermanager import OrderManager
from state import TradingState
import logging
import time
from scipy.stats import cauchy
from util.market_ticker import get_next_trading_day

class Strategy(): 

    def __init__(self, om: OrderManager, market: str, update: asyncio.Event, state: TradingState): 
        self.order_manager = om
        self.update = update 
        self.market = market 
        self.UPPER: int = 0
        self.LOWER: int = 0 
        self.state = state 
        self.buy_price = 0 

        self.EOD = 1682452800
        self.POSITION_LIMIT = 30 

        # Paramaters for Cauchy distribution
        self.x0 = 0
        self.gamma = 0.000005

    def set_eod(self): 
        day = get_next_trading_day()
        # Get UNIX timestamp for 4:00 PM EST on the next trading day; Beware of time zones 
        self.EOD = int(time.mktime(time.strptime(day + " 16:00:00", "%Y-%m-%d %H:%M:%S")))

    def set_market(self, price): 
        adj_price: int = 50 * int(price / 50) + 25
        self.market += str(adj_price)
        self.UPPER = adj_price + 25
        self.LOWER = adj_price - 25
        logging.info("Strategy set market to: " + self.market)

    async def run(self): 
        while True: 
            await self.update.wait()
            self.update.clear()

            curr_time = time.time()
            offset = self.EOD - curr_time
            curr_gamma = self.gamma*(offset)**(3/5)

            try: 
                p = cauchy.cdf((self.UPPER-self.state.sp_price)/self.state.sp_price, self.x0, curr_gamma) - cauchy.cdf((self.LOWER-self.state.sp_price)/self.state.sp_price, self.x0, curr_gamma)
                bid = round(p * 100) - 1
                ask = round(p * 100) + 2

                bid_vol = min(10, self.POSITION_LIMIT - self.state.position)
                ask_vol = min(10, self.POSITION_LIMIT + self.state.position)

                if self.state.position > 0:
                    bid -= round(self.state.position / 10)
                    ask -= round(self.state.position / 10)
                elif self.state.position < 0:
                    bid += round(-self.state.position / 10)
                    ask += round(-self.state.position / 10)

                best_bid = max(self.state.orderbook_ba["bids"].keys()) if len(self.state.orderbook_ba["bids"]) > 0 else 0
                best_ask = min(self.state.orderbook_ba["asks"].keys()) if len(self.state.orderbook_ba["asks"]) > 0 else 100

                if bid >= best_ask:
                    bid = best_ask - 1
                if ask <= best_bid:
                    ask = best_bid + 1
                
                logging.info(f"Placing order from strategy: {bid}/{bid_vol}, {ask}/{ask_vol}")
                await self.order_manager.place_order(bid, bid_vol, ask, ask_vol)

            except Exception as e: 
                logging.error(e) 
