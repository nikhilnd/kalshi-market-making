import config
import asyncio
import aiohttp
from typing import List
from state import TradingState
from ordermanager import OrderManager
from strategy import Strategy
import logging

class TDClient(): 
    """
    Client for TD Ameritrade API. Used to get the current S&P 500 price. 
    """

    def __init__(self, update: asyncio.Event, state: TradingState, om: OrderManager, strat: Strategy) -> None:
        self.REFRESH_TOKEN = config.REFRESH_TOKEN
        self.CONSUMER_KEY = config.CONSUMER_KEY
        self.base_url = "https://api.tdameritrade.com/v1/"
        self.ACCESS_TOKEN = None 
        self.price: int = -1 
        self.count: int = 0
        self.update = update
        self.state = state
        self.om = om
        self.strat = strat

        self.REFRESH_TOKEN_DELAY = 5
        self.REQUEST_DELAY = 10

    async def get_access_token(self):
        if self.ACCESS_TOKEN is None:
            logging.info("Getting access token")
            self.ACCESS_TOKEN = await self.refresh_access_token()
            logging.info("Retrieved access token")
        return self.ACCESS_TOKEN

    async def refresh_access_token(self) -> str:
        url = self.base_url + "oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.REFRESH_TOKEN,
            "client_id": self.CONSUMER_KEY + "@AMER.OAUTHAP"
        }
        # Asynchronous request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as res:
                    self.ACCESS_TOKEN = (await res.json())["access_token"]
                    return self.ACCESS_TOKEN
        except Exception as e:
            logging.error("Error refreshing access token: ", e)

            asyncio.sleep(self.REFRESH_TOKEN_DELAY)
            return await self.refresh_access_token()
    
    def update_state(self, price): 
        self.state.update_sp(price)
        self.update.set()

    async def run(self): 
        await self.get_access_token()
        try: 
            while True: 
                # Make request for current SPX quote
                url = self.base_url + "marketdata/%24SPX.X/quotes"
                extra_headers_ = {
                    "content-type": "application/json",
                    "Authorization": "Bearer " + self.ACCESS_TOKEN
                }
                try: 
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=extra_headers_) as res:
                            # Check for stale access token
                            if res.status != 200:
                                logging.info("Access token expired, refreshing")
                                await self.refresh_access_token()
                                logging.info("Access token refreshed")
                                continue 
                            
                            data = await res.json() 
                            price = data["$SPX.X"]["lastPrice"]
                            if self.price == -1: 
                                self.om.set_market(price)
                                self.strat.set_market(price)
                                self.price = price

                            self.update_state(price)
                except Exception as e:
                    logging.error(e)
                # Rate limiting
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Keyboard interrupt. Exiting TD Client...")
    
    def get_price(self):
        return self.price
    
    def get_recent_prices(self) -> List[float]:
        return self.recent_prices