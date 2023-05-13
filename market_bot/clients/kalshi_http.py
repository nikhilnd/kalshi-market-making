import requests
import json
import pandas as pd
import asyncio 
import aiohttp  
import logging
import sys

class KalshiHTTPClient:
    """
    Client for the Kalshi HTTP API. Used to place, cancel, and manage orders. 
    """

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.api_base = "https://trading-api.kalshi.com/trade-api/v2"
        self.headers = {"Content-Type": "application/json"}
        self.token = None
        self.user_id = None

        self.RETRY_LOGIN_DELAY = 1 # try again after 1 second

        self.login()
        self.failure = 0 

    def login(self):
        logging.info("Logging into Kalshi HTTP client")
        if self.token is not None and self.user_id is not None:
            return
        
        login_json = json.dumps({"email": self.email, "password": self.password})
        res = requests.post(
            self.api_base + "/login", 
            data = login_json,
            headers=self.headers
        ).json()
        if "token" in res:
            self.token = res["token"]
            self.user_id = res["member_id"]
            self.headers["Authorization"] = self.user_id + " " + self.token
            logging.info("Successfully logged in to Kalshi HTTP client")
        else:
            logging.error("Kalshi HTTP client login failed")
            if self.failure > 5:
                logging.critical("FATAL ERROR: Kalshi HTTP client login failed too many times. Exiting...")
                sys.exit(1)
            self.failure += 1

            # yield execution and try to login again after a delay
            asyncio.sleep(self.RETRY_LOGIN_DELAY)
            self.login()
    
    async def get(self, endpoint):

        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_base + endpoint, headers=self.headers) as response:
                return await response.json(), response.status

    async def post(self, endpoint, data):

        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_base + endpoint, data=json.dumps(data), headers=self.headers) as response:
                return await response.json(), response.status
    
    async def put(self, endpoint, data):

        async with aiohttp.ClientSession() as session:
            async with session.put(self.api_base + endpoint, data=json.dumps(data), headers=self.headers) as response:
                return await response.json(), response.status
    
    async def delete(self, endpoint):

        async with aiohttp.ClientSession() as session:
            async with session.delete(self.api_base + endpoint, headers=self.headers) as response:
                return await response.json(), response.status
 
    async def get_events(self, ticker=None):
        params = {"ticker": ticker}
        res, code = await self.get("/events" + "?" + "&".join([f"{k}={v}" for k, v in params.items() if v is not None]))
        return res, code
    
    async def get_markets(self,
                       tickers=None, 
                       event_ticker=None, 
                       series_ticker=None, 
                       limit=100, 
                       offset=0, 
                       status=None
                    ):
        params = {
            "tickers": tickers,
            "event_ticker": event_ticker,
            "series_ticker": series_ticker,
            "limit": limit,
            "offset": offset,
            "status": status,
        }
        res, code = await self.get("/markets" + "?" + "&".join([f"{k}={v}" for k, v in params.items() if v is not None]))
        return res, code

    async def get_market_orderbook(self, ticker, depth=10):
        res, code = await self.get(f"/markets/{ticker}/orderbook?depth={depth}")
        return res, code
    
    async def get_balance(self):
        res, code = await self.get("/portfolio/balance")
        return res["balance"], code
    
    async def get_fills(self):
        res, code = await self.get("/portfolio/fills")
        return res, code
   
    async def get_positions(self):
        res, code = await self.get("/portfolio/positions")
        return res, code
    
    async def get_portfolio_settlements(self):
        res, code = await self.get("/portfolio/settlements")
        return res, code
   
    async def get_positions_pd(self):
        res, code = await self.get_positions()
        df = pd.json_normalize(res)
        return df
    
    async def print_positions(self):
        positions_df = await self.get_positions_pd()
        market_positions = pd.json_normalize(positions_df["market_positions"][0])
        event_positions = pd.json_normalize(positions_df["event_positions"][0])
        combined_df = pd.concat([market_positions, event_positions], axis=1)
        print(combined_df)

    async def get_orders(self, market_ticker: str):
        res, code = await self.get("/portfolio/orders/?ticker=" + market_ticker + "&status=resting")
        return res, code
    
    async def get_order(self, order_id: str): 
        res, code = await self.get("/portfolio/orders/" + order_id)
        return res, code

    async def post_limit_order(self,
                    action: str,
                    ticker: str,
                    side: str, 
                    count: int,
                    order_id, 
                    yes_price=None,
                    no_price=None,
                    expiration_ts: int = None,
                    buy_max_cost=None,
                    ):
        data = {
            "action": action,
            "ticker": ticker,
            "side": side,
            "count": count,
            "client_order_id": order_id,
            "type": "limit",
            "yes_price": yes_price,
            "no_price": no_price,
            "expiration_ts": expiration_ts,
            "buy_max_cost": buy_max_cost,
        }
        try:
            res, code = await self.post("/portfolio/orders", data)
            # print("Order placed successfully!")
            return res, code
        except Exception as e:
            # print("Error placing order:", e)
            return None

    async def post_market_order(self,
                          action,
                          ticker,
                          side,
                          count,
                          order_id,
                          ):
        data = {
            "action": action,
            "ticker": ticker,
            "side": side,
            "count": count,
            "client_order_id": order_id,
            "type": "market",
        }
        try:
            res, code = await self.post("/portfolio/orders", data)
            return res, code
        except Exception as e:
            print("Error placing order:", e)
            return False # failed order, don't handle error here
    
    async def cancel_limit_order(self, order_id):
        
        try:
            resolve, code = await self.delete(f"/portfolio/orders/{order_id}")
            return resolve, code
        except Exception as e:
            print("Error canceling order:", e)
            return False # failed cancel, don't handle error here

    async def get_positions(self, market: str): 
        res, code = await self.get("/portfolio/positions/?ticker=" + market)
        return res, code
