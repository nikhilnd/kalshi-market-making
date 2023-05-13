import asyncio
from ordermanager import OrderManager
from clients.kalshi_http import KalshiHTTPClient
import logging

class TradingState(): 

    def __init__(self, om: OrderManager, kalshi: KalshiHTTPClient): 

        self.orderbook_ba = {
            "bids": {}, 
            "asks": {}
        }

        self.position: int = 0
        self.sp_price: float = -1 
        self.om = om
        self.last_update = ""
        self.kalshi = kalshi

    def update_sp(self, price: float): 
        self.sp_price = price
        self.last_update = "sp"
        logging.info(f"Received S&P update to price {price}")
    
    def set_orderbook(self, orderbook): 

        self.orderbook_ba["bids"] = {}
        self.orderbook_ba["asks"] = {}

        if "yes" in orderbook: 
            for bid in orderbook["yes"]: 
                self.orderbook_ba["bids"][bid[0]] = bid[1]
        
        if "no" in orderbook: 
            for ask in orderbook["no"]: 
                self.orderbook_ba["asks"][100 - ask[0]] = ask[1]

        self.last_update = "kalshi"
        logging.info(f"Received Kalshi orderbook snapshot: {self.orderbook_ba}")
        self.om.interupted = True
    
    def update_orderbook(self, delta): 
        price = delta["price"]
        change = delta["delta"]
        side = delta["side"]

        if side == "no": 
            price = 100 - price
            if price in self.orderbook_ba["asks"]: 
                self.orderbook_ba["asks"][price] += change
            else:
                self.orderbook_ba["asks"][price] = change
            
            if self.orderbook_ba["asks"][price] == 0: 
                del self.orderbook_ba["asks"][price]
        else:
            if price in self.orderbook_ba["bids"]: 
                self.orderbook_ba["bids"][price] += change
            else:
                self.orderbook_ba["bids"][price] = change

            if self.orderbook_ba["bids"][price] == 0:
                del self.orderbook_ba["bids"][price]
        
        self.last_update = "kalshi"
        logging.info(f"Received Kalshi orderbook delta: {self.orderbook_ba}")
        self.om.interupted = True

    def update_position(self, fill):
        side = fill["side"]
        count = fill["count"]
        if side == "yes":
            self.position += count
        else:
            self.position -= count
        
        self.om.update_resting(fill, side, count)
        logging.info(f"Received fill for {count} on {side}. Updated position to {self.position}")