from freqtrade_client import FtRestClient
import pandas as pd
from pprint import pprint

client = FtRestClient("http://127.0.0.1:8080", "freqtrader", "1234")

# Get the status of the bot
ping = client.ping()
print(ping)

strategy = "SampleStrategy"
strategy_timeframe = client.strategy(strategy)["timeframe"]
candles = client.pair_candles("BTC/USDT", strategy_timeframe, 10000)
# pprint(candles.keys())

# available_pairs = client.pairlists_available()
# pprint(available_pairs)
# available_pairs = client.available_pairs(strategy_timeframe, "USDT")
# pprint(available_pairs)

# Convert the response to a DataFrame
columns = candles['columns']
data = candles['data']
df = pd.DataFrame(data, columns=columns)

# Convert 'date' column to datetime for easier manipulation
df['date'] = pd.to_datetime(df['date'])

print(df.columns)
# # Example output
# print(df[["date", "close"]].iloc[:3])
# # Example output
# print(df[["date", "close"]].iloc[-3:])
