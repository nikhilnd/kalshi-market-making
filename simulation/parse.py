import dateparser
import pandas as pd
import json

"""
Parse historical data from the PostgreSQL database into a csv file that can be used to simulate trading. 
"""

# Convert date to unix timestamp
def convertDate(date) -> float:
    return dateparser.parse(date).timestamp()

"""
Step 1: Group delta messages into fills or cancellations
Approach: 
1. Iterate through trades to make an ordered list of all trades; store quantity, taker side, timestamp and taker price
2. Iterate through deltas. If delta is negative, check if quantity matches next trade and timestamp is equal to.
3. If so, set fill to true.
"""

# Read in data
df = pd.read_csv("kalshi.csv")
df['message'] = df['message'].str.replace("'", '\"')

trades = []

# Make list of trades 
for index, row in df.iterrows():
    data = json.loads(row['message'])
    if data['type'] == 'trade':
        timestamp = data['msg']['ts']
        side = data['msg']['taker_side']
        quantity = data['msg']['count']
        taker_price = data['msg']['no_price'] if side == 'no' else data['msg']['yes_price']
        trades.append((timestamp, side, quantity, taker_price))

print(trades[0])
df_fills = pd.DataFrame(columns=['timestamp', 'ticker', 'message', 'fill'])

count = 0

# Create dataframe of all trades 
for index, row in df.iterrows():
    data = json.loads(row['message'])
    if data['type'] == 'orderbook_delta':
        timestamp = row['timestamp']
        ts = int(convertDate(timestamp))
        ticker = row['market_ticker']
        side = data['msg']['side']
        quantity = data['msg']['delta']
        price = data['msg']['price']
        if (quantity < 0) and count < len(trades) and (-quantity == trades[count][2]) and (abs(ts - trades[count][0]) <= 1) and side != trades[count][1] and price == (100 - trades[count][3]): 
            count += 1
            print(count)
            df_fills = pd.concat([df_fills, pd.DataFrame({'timestamp': timestamp, 'ticker': ticker, 'message': json.dumps(data), 'fill': True}, index=[0])], ignore_index=True)
        else:
            df_fills = pd.concat([df_fills, pd.DataFrame({'timestamp': timestamp, 'ticker': ticker, 'message': json.dumps(data), 'fill': False}, index=[0])], ignore_index=True)
            if (quantity < 0) and count >= len(trades): 
                print("burn")
    elif data['type'] == 'orderbook_snapshot': 
        df_fills = pd.concat([df_fills, pd.DataFrame({'timestamp': row['timestamp'], 'ticker': row['market_ticker'], 'message': json.dumps(data), 'fill': False}, index=[0])], ignore_index=True)

events = pd.DataFrame(columns=['Time','Competitor','Operation','OrderId','Instrument','Side','Volume','Price','Lifespan','Fee'])
orderId = 0
# Parse message and make structured Dataframe of market events 
for index, row in df_fills.iterrows():
    print(index)
    newRow = []
    data = json.loads(row['message'])
    msg = data['msg']
    if data["type"] == "orderbook_snapshot": 

        for order in msg["yes"]: 
            newRow = [row['timestamp'], "", "Insert", orderId, 1, "B", order[1], order[0] * 100, "G", 0]
            events.loc[len(events)] = newRow
            orderId += 1
        
        for order in msg["no"]:
            newRow = [row['timestamp'], "", "Insert", orderId, 1, "A", order[1], (100 - order[0]) * 100, "G", 0]
            events.loc[len(events)] = newRow
            orderId += 1
        
    elif data['type'] == 'orderbook_delta': 
        side = msg["side"]
        delta = msg["delta"]
        price = msg["price"]

        if side == "yes": 
            if delta > 0: 
                newRow = [row['timestamp'], "", "Insert", orderId, 1, "B", delta, price * 100, "G", 0]
            elif row['fill'] == True:
                newRow = [row['timestamp'], "", "Insert", orderId, 1, "A", -delta, price * 100, "G", 0]
            else: 
                newRow = [row['timestamp'], "", "Cancel", orderId, 1, "B", -delta, price * 100, "G", 0]
        else: 
            if delta > 0: 
                newRow = [row['timestamp'], "", "Insert", orderId, 1, "A", delta, (100 - price) * 100, "G", 0]
            elif row['fill'] == True: 
                newRow = [row['timestamp'], "", "Insert", orderId, 1, "B", -delta, (100 - price) * 100, "G", 0]
            else: 
                # Implicit cancel
                newRow = [row['timestamp'], "", "Cancel", orderId, 1, "A", -delta, (100 - price) * 100, "G", 0]
        events.loc[len(events)] = newRow
        orderId += 1
        
# Read in S&P 500 
df_sp = pd.read_csv("sp.csv")
df_sp['message'] = df_sp['message'].str.replace("'", '\"')
df_sp['message'] = df_sp['message'].str.replace("True", '\"True\"')
df_sp['message'] = df_sp['message'].str.replace("False", '\"false\"')

sp_events = pd.DataFrame(columns=['Time','Competitor','Operation','OrderId','Instrument','Side','Volume','Price','Lifespan','Fee'])

# Parse message and make structured Dataframe of market events
for index, row in df_sp.iterrows():
    newRow = []
    data = json.loads(row['message'])
    price = data['$SPX.X']['lastPrice']
    newRow = [row['timestamp'], "", "", "", 0, "", "", price, "", ""]
    sp_events.loc[len(sp_events)] = newRow

# Combine Kalshi events and S&P 500 events
df_combined = pd.concat([events, sp_events], ignore_index=True)
df_combined = df_combined.sort_values(by=['Time'])
df_combined.to_csv('combined.csv', index=False)