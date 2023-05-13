import asyncio 
from clients.kalshi_http import KalshiHTTPClient
import uuid 
import sys
import logging

class OrderManager(): 
    
    def __init__(self, kalshi: KalshiHTTPClient, market: str): 
        self.kalshi = kalshi
        self.resting_orders = {
            "yes": {
                "id": None, 
                "price": None,
                "count": None
            }, 
            "no": {
                "id": None,
                "price": None,
                "count": None
            }
        }
        self.market = market 
        self.failure_count = 0
        self.trading = True
        self.interupted = False

    def set_market(self, price): 
        adj_price: int = 50 * int(price / 50) + 25
        self.market += str(adj_price)
        logging.info("OM set market to: " + self.market)
    
    async def handle_failure(self): 
        """
        Cancel all orders and reboot system
        """
        # Reload connection, prevent any new orders from being placed
        logging.info("Reloading connection to Kalshi HTTP client")
        self.trading = False
        await asyncio.sleep(1)
        self.kalshi.login()
        logging.info("Cancelling all orders")
        await self.cancel_all_orders()
        logging.info("Successfully cancelled all orders")
        self.trading = True

    async def cancel_all_orders(self): 
        orders, code = await self.kalshi.get_orders(self.market)

        if code != 200: 
            logging.error("Failed to cancel all orders, retrying...")
            self.failure_count += 1 
            if self.failure_count > 5:
                logging.critical("FATAL ERROR: Failed to cancel all orders too many times. Exiting...")
                sys.exit(1)

            await self.handle_failure()

        for order in orders['orders']: 
            await self.kalshi.cancel_limit_order(order['client_order_id'])

    async def cancelYes(self): 
        logging.info("Cancelling existing yes order")
        res, code = await self.kalshi.cancel_limit_order(self.resting_orders["yes"]["id"])
        print(res)

        if code != 200:
            logging.error("Failed to cancel yes order, reloading Order Manager")
            await self.handle_failure() 
            return

        self.resting_orders["yes"]["id"] = None

    async def cancelNo(self):
        logging.info("Cancelling existing no order")
        res, code = await self.kalshi.cancel_limit_order(self.resting_orders["no"]["id"])
        print(res)

        if code != 200: 
            logging.error("Failed to cancel no order, reloading Order Manager")
            await self.handle_failure() 
            return
        
        self.resting_orders["no"]["id"] = None

    def update_resting(self, fill, side, count): 

        if side == "yes": 
            self.resting_orders["yes"]["count"] -= count
            if self.resting_orders["yes"]["count"] == 0: 
                self.resting_orders["yes"]["id"] = None
                self.resting_orders["yes"]["price"] = None
        elif side == "no": 
            self.resting_orders["no"]["count"] -= count
            if self.resting_orders["no"]["count"] == 0: 
                self.resting_orders["no"]["id"] = None
                self.resting_orders["no"]["price"] = None

    async def place_order(self, bid_price, bid_count, ask_price, ask_count): 
        
        if not self.trading: 
            return
        self.interupted = False 

        yes_price = bid_price
        yes_count = bid_count

        no_price = 100 - ask_price
        no_count = ask_count

        if (yes_price != self.resting_orders["yes"]["price"] or yes_count != self.resting_orders["yes"]["count"]) and yes_count > 0: 
            # Cancel old order if it exists
            if self.resting_orders["yes"]["id"] is not None or yes_price > 99: 
                await self.cancelYes()
            
            if self.interupted:
                self.interupted = False 
                logging.info("New information received, cancelling orders")
                self.cancel_all_orders()
                return

            if yes_price <= 99 and yes_price >= 1: 
                logging.info(f"Placing new yes order: {yes_price} at {yes_count}")
                id = str(uuid.uuid4())

                res, code = await self.kalshi.post_limit_order("buy", self.market, "yes", yes_count, id, yes_price=yes_price)

                if code != 201 and res['error']['code'] != "insufficient_balance": 
                    logging.error(f"Failed to place yes order, {res['error']['message']}, reloading Order Manager")
                    await self.handle_failure() 
                    return 
                elif code != 201: 
                    # Insufficient balance, only place no order 
                    logging.error(f"Failed to place yes order, {res['error']['message']}.") 
                else: 
                    self.resting_orders["yes"]["id"] = res["order"]["order_id"]
                    self.resting_orders["yes"]["price"] = yes_price
                    self.resting_orders["yes"]["count"] = yes_count

                    if self.interupted:
                        self.interupted = False 
                        logging.info("New information received, cancelling orders")
                        self.cancel_all_orders()
                        return

                    logging.info(f"Successfully placed order, current resting orders: {self.resting_orders}")

    
        if (no_price != self.resting_orders["no"]["price"] or no_count != self.resting_orders["no"]["count"]) and no_count > 0:
            if self.resting_orders["no"]["id"] is not None or no_price > 99: 
                await self.cancelNo()

            if self.interupted:
                self.interupted = False 
                logging.info("New information received, cancelling orders")
                self.cancel_all_orders()
                return

            if no_price <= 99 and no_price >= 1:
                logging.info(f"Placing new no order: {no_price} at {no_count}")
                id = str(uuid.uuid4())

                res, code = await self.kalshi.post_limit_order("buy", self.market, "no", no_count, id, no_price=no_price)

                if code != 201 and res['error']['code'] != "insufficient_balance":
                    logging.error(f"Failed to place no order, {res['error']['message']}, reloading Order Manager")
                    self.handle_failure()
                    return
                elif code != 201: 
                    logging.error(f"Failed to place no order, {res['error']['message']}.")
                else: 
                    self.resting_orders["no"]["id"] = res["order"]["order_id"]
                    self.resting_orders["no"]["price"] = no_price
                    self.resting_orders["no"]["count"] = no_count

                    if self.interupted:
                        self.interupted = False 
                        logging.info("New information received, cancelling orders")
                        self.cancel_all_orders()
                        return

                    logging.info(f"Successfully placed order, current resting orders: {self.resting_orders}")