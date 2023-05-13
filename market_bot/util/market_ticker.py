import datetime
import pytz
import pandas_market_calendars as mcal
import pandas as pd 
import time 

def is_market_open() -> bool:
    nyse = mcal.get_calendar('NYSE')
    now = datetime.datetime.now()
    market_schedule = nyse.schedule(start_date=now, end_date=now)
    market_schedule["market_open"] = pd.to_datetime(market_schedule["market_open"]).dt.tz_localize('US/Eastern')
    market_schedule["market_close"] = pd.to_datetime(market_schedule["market_close"]).dt.tz_localize('US/Eastern')
    market_open_range = mcal.date_range(market_schedule, frequency='1min')

    # check if this is not a trading day
    if market_open_range.empty:
        return False

    # convert the current time to UTC (standardized timing)
    now = now.astimezone(pytz.timezone('UTC'))

    return not market_open_range.empty and (market_open_range[0] <= now <= market_open_range[-1])

def get_next_trading_day() -> datetime.date:
    nyse = mcal.get_calendar('NYSE')
    now = datetime.datetime.now()
    if is_market_open():
        return now.date()
    else:
        next_day = now.date() + datetime.timedelta(days=1)
        next_schedule = nyse.schedule(start_date=next_day, end_date=next_day + datetime.timedelta(days=10))
        next_schedule = next_schedule.tz_localize('US/Eastern')
        return next_schedule.iloc[0].name.date()

def round_to_nearest_25_or_75(price: float) -> int:
    price = int(price)
    remainder = price % 100
    if remainder <= 50:
        return price - remainder + 25
    else:
        return price - remainder + 75

def get_market_ticker():
    market_date = get_next_trading_day()
    market_date_str = market_date.strftime("%y%b%d").upper()

    market_ticker = ""
    # Check if market_date is a Friday
    if market_date.weekday() == 4:
        market_ticker = f"INXW-{market_date_str}-B"
    else:
        market_ticker = f"INXD-{market_date_str}-B"

    return market_ticker

# Unit tests
if __name__ == '__main__':
    print(is_market_open())
    print(get_market_ticker(2400))
    print(get_next_trading_day())
    print(int(time.mktime(time.strptime(str(get_next_trading_day()) + " 16:00:00", "%Y-%m-%d %H:%M:%S"))))