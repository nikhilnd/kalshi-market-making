import asyncio
from clients.kalshi_ws import KalshiClient
from state import TradingState
from clients.kalshi_http import KalshiHTTPClient
from clients.td import TDClient
from strategy import Strategy
from ordermanager import OrderManager
import config 
from util.market_ticker import get_market_ticker, get_next_trading_day
import logging
import sys
import time
import datetime

email = config.email
password = config.password
api_base = "https://trading-api.kalshi.com/trade-api/v2" 
ws_base = "wss://trading-api.kalshi.com/trade-api/ws/v2" 

async def main():

    logging.basicConfig(filename='trading.log', filemode='w', format='%(asctime)s - %(levelname)s - %(message)s - %(funcName)s', level=logging.DEBUG)

    # Comment out to disable logging to console
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    # Wait until the market is open 
    next_day: int = int(time.mktime(time.strptime(str(get_next_trading_day()) + " 09:30:00", "%Y-%m-%d %H:%M:%S")))
    seconds: int = next_day - int(time.mktime(datetime.datetime.now().timetuple()))
    logging.info(f"{seconds} seconds until market open.")
    time.sleep(seconds)
    logging.info("Market open, starting execution...")

    logging.info("Kalshi Trading System v1")

    MARKET = get_market_ticker()

    update = asyncio.Event()
    
    kalshi_http_client = KalshiHTTPClient(email, password)
    om = OrderManager(kalshi_http_client, MARKET)
    state = TradingState(om, kalshi_http_client)
    strategy = Strategy(om, MARKET, update, state)
    td_client = TDClient(update, state, om, strategy)
    kalshi_client = KalshiClient(api_base, ws_base, email, password, td_client, state, update, MARKET)

    td = asyncio.create_task(td_client.run())
    kalshi = asyncio.create_task(kalshi_client.run())
    strat = asyncio.create_task(strategy.run())

    await td
    await kalshi
    await strat

if __name__ == "__main__":
    asyncio.run(main())