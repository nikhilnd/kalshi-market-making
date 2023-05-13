class TradingState(): 

    def __init__(self, start: int) -> None:
        self.orderbook = {
            "bids": {}, 
            "asks": {}
        }

        self.sp_price: float = -1 
        self.position: int = 0
        self.pnl = 0 

        self.yes: int = 0
        self.no: int = 0
        self.total_yes_price: float = 0 
        self.total_no_price: float = 0
        self.min = min
        self.max = max
        # Hardcoded start of trading day value 
        self.time = start

        self.bid = {
            "price": 0, 
            "quantity": 0, 
            "queue": 0
        }

        self.ask = {
            "price": 0,
            "quantity": 0,
            "queue": 0
        } 

    def getSP(self) -> float: 
        return self.sp_price

    def getOrderbook(self): 
        return self.orderbook

    def cancelOrder(self, side) -> None: 
        if side == "B": 
            if self.bid["quantity"] != 0: 
                # Update order book
                price = self.bid["price"]
                self.orderbook["bids"][price] -= self.bid["quantity"]
                if self.orderbook["bids"][price] == 0:
                    del self.orderbook["bids"][price]

                # Zero out quantity and queue 
                self.bid["quantity"] = 0
                self.bid["queue"] = 0

        elif side == "A": 
            if self.ask["quantity"] != 0: 
                price = self.ask["price"]

                self.orderbook["asks"][price] -= self.ask["quantity"]
                if self.orderbook["asks"][price] == 0:
                    del self.orderbook["asks"][price]

                self.ask["quantity"] = 0
                self.ask["queue"] = 0

    def insertOrder(self, side, price, quantity) -> None: 
        if side == "B": 
            
            if price != self.bid["price"] or quantity != self.bid["quantity"]:
                self.cancelOrder("B")

            self.bid["price"] = price
            self.bid["quantity"] = 0
            self.bid["queue"] = 0

            self.updateOrderbook("B", price, quantity, "Insert", True)

        elif side == "A": 
            
            if price != self.ask["price"] or quantity != self.ask["quantity"]:
                self.cancelOrder("A")

            self.ask["price"] = price
            self.ask["quantity"] = 0
            self.ask["queue"] = 0

            self.updateOrderbook("A", price, quantity, "Insert", True)

    def updateSP(self, price) -> None: 
        self.sp_price = price

    def updateOrderbook(self, side, price, vol, type, bot) -> None: 

        if type == "Cancel": 
            if side == "A" and price in self.orderbook["asks"]: 
                    
                    # Can only cancel as much quantity as is in the orderbook
                    cancelVolume = min(vol, self.orderbook["asks"][price])

                    # Don't want to cancel bot orders
                    if self.ask["price"] == price and self.ask["quantity"] != 0:
                        cancelVolume -= self.ask["quantity"]

                    self.orderbook["asks"][price] -= cancelVolume
                    if self.orderbook["asks"][price] == 0: 
                        del self.orderbook["asks"][price]
            elif side == "B" and price in self.orderbook["bids"]: 
                    cancelVolume = min(vol, self.orderbook["bids"][price])
                    if self.bid["price"] == price and self.bid["quantity"] != 0:
                        cancelVolume -= self.bid["quantity"]

                    self.orderbook["bids"][price] -= cancelVolume
                    if self.orderbook["bids"][price] == 0: 
                        del self.orderbook["bids"][price]
        
        elif type == "Insert": 
             
            # Check if the order results in a fill (with best resting bid/ask) 
            fillStatus = self.checkFill(side, price, vol)

            if fillStatus and side == "A": 

                # Walk the book: 
                remVol = vol
                bestBid = max(self.orderbook["bids"])
                while remVol > 0 and bestBid >= price: 
                    fillVolume = min(remVol, self.orderbook["bids"][bestBid])

                    if self.bid["price"] == bestBid and self.bid["quantity"] != 0:
                        botFill = min(fillVolume - self.bid["queue"] + 1, self.bid["quantity"])

                        if botFill > 0: 
                            # Update bot order quantity and queue position
                            self.bid["quantity"] = max(0, self.bid["quantity"] - botFill)
                            self.bid["queue"] = max(1, self.bid["queue"] - fillVolume)
                            self.position += botFill

                            self.yes += botFill
                            self.total_yes_price += botFill * (self.bid["price"] / 100)

                            # Yes resolution 
                            if self.sp_price >= self.min and self.sp_price <= self.max:
                                self.pnl = (self.yes - self.total_yes_price) - (self.total_no_price)
                            # No resolution
                            else: 
                                self.pnl = (self.no - self.total_no_price) - (self.total_yes_price)

                            # self.pnl -= botFill * (self.bid["price"] / 100)

                            print(f"Bot bid order filled. {botFill} at {bestBid}. Current position: {self.position}")
                            print(f"Current PnL: {self.pnl}")
                    
                    # Bot market order
                    elif bot: 
                        self.position -= fillVolume

                        self.no += fillVolume
                        self.total_no_price += fillVolume * ((100 - bestBid) / 100)

                        # Yes resolution
                        if self.sp_price >= self.min and self.sp_price <= self.max:
                            self.pnl = (self.yes - self.total_yes_price) - (self.total_no_price)
                        # No resolution
                        else:
                            self.pnl = (self.no - self.total_no_price) - (self.total_yes_price)

                        # self.pnl += fillVolume * (bestBid / 100)
                        print(f"Bot market ask order filled. {fillVolume} at {bestBid}. Current position: {self.position}")
                        print(f"Current PnL: {self.pnl}")

                    self.orderbook["bids"][bestBid] -= fillVolume
                    remVol -= fillVolume
                    if self.orderbook["bids"][bestBid] == 0: 
                        del self.orderbook["bids"][bestBid]

                    if len(self.orderbook["bids"]) == 0:
                        break

                    bestBid = max(self.orderbook["bids"])
                
                # If there is still volume left, insert the remainder into the orderbook
                if remVol > 0: 
                    if price in self.orderbook["asks"]: 
                        self.orderbook["asks"][price] += remVol
                    else:
                        self.orderbook["asks"][price] = remVol

                    # Bot market order with remaining volume
                    if bot: 
                        self.ask["quantity"] = remVol
                        self.ask["queue"] = 1
            
            elif fillStatus and side == "B": 

                remVol = vol
                bestAsk = min(self.orderbook["asks"])
                while remVol > 0 and bestAsk <= price: 
                    fillVolume = min(remVol, self.orderbook["asks"][bestAsk])

                    if self.ask["price"] == bestAsk and self.ask["quantity"] != 0:
                        botFill = min(fillVolume - self.ask["queue"] + 1, self.ask["quantity"])

                        if botFill > 0: 
                            # Update bot order quantity and queue position
                            self.ask["quantity"] = max(0, self.ask["quantity"] - botFill)
                            self.ask["queue"] = max(1, self.ask["queue"] - fillVolume)
                            self.position -= botFill

                            self.no += botFill
                            self.total_no_price += botFill * ((100 - bestAsk) / 100)

                            # Yes resolution
                            if self.sp_price >= self.min and self.sp_price <= self.max:
                                self.pnl = (self.yes - self.total_yes_price) - (self.total_no_price)
                            # No resolution
                            else:
                                self.pnl = (self.no - self.total_no_price) - (self.total_yes_price)

                            # self.pnl += botFill * (self.ask["price"] / 100)

                            print(f"Bot ask order filled. {botFill} at {bestAsk}. Current position: {self.position}")
                            print(f"Current PnL: {self.pnl}")
                    
                    # Bot market order
                    elif bot: 
                        self.position += fillVolume

                        self.yes += fillVolume
                        self.total_yes_price += fillVolume * (bestAsk / 100)

                        # Yes resolution
                        if self.sp_price >= self.min and self.sp_price <= self.max:
                            self.pnl = (self.yes - self.total_yes_price) - (self.total_no_price)
                        # No resolution
                        else:
                            self.pnl = (self.no - self.total_no_price) - (self.total_yes_price)

                        # self.pnl -= fillVolume * (bestAsk / 100)
                        print(f"Bot market bid order filled. {fillVolume} at {bestAsk}. Current position: {self.position}")
                        print(f"Current PnL: {self.pnl}")

                    self.orderbook["asks"][bestAsk] -= fillVolume
                    remVol -= fillVolume
                    if self.orderbook["asks"][bestAsk] == 0: 
                        del self.orderbook["asks"][bestAsk]

                    if len(self.orderbook["asks"]) == 0:
                        break

                    bestAsk = min(self.orderbook["asks"])
                
                # If there is still volume left, insert the remainder into the orderbook
                if remVol > 0: 
                    if price in self.orderbook["bids"]: 
                        self.orderbook["bids"][price] += remVol
                    else:
                        self.orderbook["bids"][price] = remVol

                    # Bot market order with remaining volume
                    if bot: 
                        self.bid["quantity"] = remVol
                        self.bid["queue"] = 1
            
            # No fill, simply update orderbook
            else: 
                if side == "A": 
                    
                    # Set bot order quantity and queue position
                    if bot: 
                        self.ask["quantity"] = vol
                        self.ask["queue"] = 1 if price not in self.orderbook["asks"] else self.orderbook["asks"][price] + 1

                    if price in self.orderbook["asks"]: 
                        self.orderbook["asks"][price] += vol
                    else:
                        self.orderbook["asks"][price] = vol
                elif side == "B": 
                    
                    # Set bot order quantity and queue position
                    if bot:
                        self.bid["quantity"] = vol
                        self.bid["queue"] = 1 if price not in self.orderbook["bids"] else self.orderbook["bids"][price] + 1

                    if price in self.orderbook["bids"]: 
                        self.orderbook["bids"][price] += vol
                    else:
                        self.orderbook["bids"][price] = vol

    def checkFill(self, side, price, vol) -> bool: 
        if side == "A": 
            if len(self.orderbook["bids"]) > 0 and price <= max(self.orderbook["bids"]): 
                return True
            else:
                return False
        elif side == "B": 
            if len(self.orderbook["asks"]) > 0 and price >= min(self.orderbook["asks"]): 
                return True
            else:
                return False
    
    def setOrderbook(self, orderbook) -> None: 
        self.orderbook = orderbook
                