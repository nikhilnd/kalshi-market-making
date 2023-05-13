import asyncio
import websockets
import json
import requests
from clients.td import TDClient
from state import TradingState
import logging

class KalshiClient():
    """
    Client for connecting to the Kalshi websocket API. Listens for updates to the orderbook and fills.
    Updates the internal state of the trading bot.  
    """
    
    def __init__(
        self,
        api_base: str,
        ws_base: str,
        email: str,
        password: str, 
        td_client: TDClient, 
        state: TradingState, 
        update: asyncio.Event, 
        market: str 
    ):
        """
            Initialize the socket object
        """

        # APIs 
        self.api_base_ = api_base
        self.ws_base_ = ws_base

        # Authenticaion 
        self.email_ = email
        self.password_ = password
        self.token_ = None
        self.member_id_ = None
        self.extra_headers_ = {"content-type": "application/json"}

        self.RETRY_DELAY = 1 # try again after 1 seconds

        # Websockets 
        self.subscriptions_ = {}
        self.id_ = 1
        self._ws = None
        self._running = False
        self.market = market
        self._loop = None
        self._sid = None

        # State 
        self.td_client = td_client
        self.ob_seq_ = -1 # sequence number of the last orderbook message received
        self.state = state 
        self.update = update
        self.error_count = 0 # number of errors in a row

        logging.info("Initialized web socket...")

    async def login(self):
        if self.token_ is not None: return

        logging.info("Logging into Kalshi...")

        login_json = json.dumps({"email": self.email_, "password": self.password_})
        
        # Blocking HTTP request 
        with requests.Session() as s:
            try:
                response = s.post(self.api_base_ + "/login", data=login_json, headers=self.extra_headers_).json()

                if 'token' in response:
                    logging.info("Success logging in to Kalshi! Bearer token obtained.")
                    self.token_ = response["token"]
                    self.member_id_ = response["member_id"]

                    # update the extra headers
                    self.extra_headers_["Authorization"] = "Bearer " + self.token_
                else:
                    logging.error("Failed to log in to Kalshi!")
                    await self.relogin()

            except Exception as e:
                print("Failed to login:", e)
                await self.relogin()

    async def relogin(self):
        self.error_count+=1 # increment error count
        asyncio.sleep(self.RETRY_DELAY)
        await self.login()

    async def start_connection(self): 
        await self.login()
        await self.connect()
        logging.info("Successfully started connection")

    async def connect(self): 
        if not self.token_: return
        logging.info("Connecting to websocket...")
        self._ws = await websockets.connect(self.ws_base_, extra_headers=self.extra_headers_, ping_interval=5, ping_timeout=5)
        logging.info("Connected to websocket!")

    async def subscribe(self): 
        try: 
            while self.td_client.get_price() == -1: 
                await asyncio.sleep(0.5)

            market_price = 50 * int(self.td_client.get_price() / 50) + 25
            # TODO: Dynamically generated ticker
            self.market += str(market_price)

            logging.info(f"Subscribing to market {self.market}")

            req = {
                "id": self.id_
                , "cmd": "subscribe"
                , "params": {
                    "channels": ["orderbook_delta", "fill"]
                    , "market_ticker": self.market
                }
            }
            self.id_ += 1
            await self._ws.send(json.dumps(req))
            res = await self._ws.recv()
            self._sid = json.loads(res)["msg"]["sid"]
        except Exception as e:
            print("Failed to subscribe:", e)
            await self.resubscribe()

    async def resubscribe(self):
        self.error_count+=1

        asyncio.sleep(self.RETRY_DELAY)

        print("\nAttempting to resubscribe...")
        await self.subscribe()
    
    async def _consume(self):
        while True:
            try:
                r = await asyncio.wait_for(self._ws.recv(), 5)
                data = json.loads(r)

                if data["type"] == "orderbook_delta" or data["type"] == "orderbook_snapshot":
                    msgSeq = data["seq"]

                    if msgSeq != (self.ob_seq_ + 1) and self.ob_seq_ != -1: 
                        logging.warning("Out of order message received, restarting connection...")
                        await self.close()
                        self._running = False
                        break

                    self.ob_seq_ = msgSeq
                elif data["type"] == "subscribed": 
                    continue  

                self.update_state(r)
            except asyncio.TimeoutError:
                break

    def update_state(self, message): 
        data = json.loads(message)
        if data["type"] == "orderbook_snapshot": 
            self.state.set_orderbook(data["msg"])
        elif data["type"] == "orderbook_delta": 
            self.state.update_orderbook(data["msg"])
        elif data["type"] == "fill": 
            self.state.update_position(data["msg"])

        self.update.set()

    
    async def run(self):
        while True:
            try:
                if not self._running:
                    await self.start_connection()
                    await self.subscribe()
                    self._running = True
                await self._consume()
            except websockets.WebSocketException as wse:
                logging.warning("Connection dropped, restarting...")
                await self.close()
                self._running = False

    async def close(self) -> None:
        """
            Close the socket (You can't resume it later)
        """
        if self._ws:
            await self._ws.close()
            self._ws = None
            self._running = False