import logging
from freqtrade_client import FtRestClient
import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time
from decimal import Decimal
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def sleep_until_target_time(scd_last_freqtrade_timestamp: datetime, last_freqtrade_timestamp: datetime):

    # Ensure all datetimes are timezone-aware in UTC
    if scd_last_freqtrade_timestamp.tzinfo is None:
        scd_last_freqtrade_timestamp = scd_last_freqtrade_timestamp.replace(tzinfo=timezone.utc)
    if last_freqtrade_timestamp.tzinfo is None:
        last_freqtrade_timestamp = last_freqtrade_timestamp.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)

    # Log timestamps
    logging.info(f"Second last recorded timestamp from Freqtrade: {scd_last_freqtrade_timestamp}")
    logging.info(f"Last recorded timestamp from Freqtrade       : {last_freqtrade_timestamp}")
    logging.info(f"UTC timestamp                                : {now_utc}")

    # Calculate time delta
    time_delta = last_freqtrade_timestamp - scd_last_freqtrade_timestamp
    wait_time = 2 * time_delta + timedelta(seconds=10)
    target_time = last_freqtrade_timestamp + wait_time

    # Calculate how long to sleep
    sleep_seconds = (target_time - now_utc).total_seconds()

    if sleep_seconds > 0:
        logging.info(f"Sleeping for {sleep_seconds:.2f} seconds until {target_time} UTC")
        time.sleep(sleep_seconds)
    else:
        logging.warning(f"Target time {target_time} is in the past. No sleep needed.")


# Helper to convert values to DynamoDB-compatible types
def convert_to_dynamodb_type(value):
    if pd.isna(value):
        return None
    elif isinstance(value, (int, float, np.integer, np.floating)):
        return Decimal(str(value))
    elif isinstance(value, Decimal):
        return value
    else:
        return str(value)


# Push the data to DynamoDB
def push_to_dynamodb(df):
    dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')
    table = dynamodb.Table('TradingApp-table1')

    with table.batch_writer() as batch:
        for index, row in tqdm(df.iterrows(), total=len(df), desc="Uploading to DynamoDB"):
            item = {}

            # Set the partition key
            item['TradingApp-table1-partitionkey'] = str(index)

            # Include index as timestamp if it's datetime-like
            item['timestamp'] = str(index)

            # Add all columns dynamically
            for col in df.columns:
                value = convert_to_dynamodb_type(row[col])
                if value is not None:
                    item[col] = value

            batch.put_item(Item=item)


def main():

    # initialize freqtrade stuff
    freqtrade_client = FtRestClient("http://127.0.0.1:8080", "freqtrader", "1234")
    strategy = "SampleStrategy"
    strategy_timeframe = freqtrade_client.strategy(strategy)["timeframe"]
    pair = "BTC/USDT"

    # get the status of the bot (should log "pong" if ok)
    logging.info(freqtrade_client.ping())

    # get data from freqtrade
    candles = None
    while candles is None:
        try:
            candles = freqtrade_client.pair_candles(pair, strategy_timeframe, 10)
        except Exception as e:
            logging.error(f"Failed to fetch candles: \n{e}", exc_info=True)
            time.sleep(5)  # wait a bit before retrying

    # convert the response to a DataFrame
    columns = candles['columns']
    data = candles['data']
    df = pd.DataFrame(data, columns=columns)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)

    # get last datetime from freqtrade df
    last_freqtrade_timestamp = df.index[-1]  # Last index
    scd_last_freqtrade_timestamp = df.index[-2]  # Second last index

    # push to dynamodb
    try:
        push_to_dynamodb(df)
        logging.info(f"Timestamp of last pushed to dynamoDB         : {df.index[-1]}")
    except Exception as e:
        logging.error(f"Failed to push data to DynamoDB: {e}", exc_info=True)

    while True:
        logging.info("Starting loop")

        # wait for correct time to proceed in loop
        sleep_until_target_time(scd_last_freqtrade_timestamp, last_freqtrade_timestamp)

        # get data from freqtrade
        try:
            candles = freqtrade_client.pair_candles(pair, strategy_timeframe, 10)

            # convert the response to a DataFrame
            columns = candles['columns']
            data = candles['data']
            df = pd.DataFrame(data, columns=columns)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # Get last datetime from freqtrade df
            last_freqtrade_timestamp = df.index[-1]  # Last index
            scd_last_freqtrade_timestamp = df.index[-2]  # Second last index

        except Exception as e:
            logging.error(f"Failed to fetch or format candles: \n{e}", exc_info=True)
            time.sleep(5)  # wait a bit before continuing
            continue

        # push to dynamodb
        try:
            push_to_dynamodb(df.iloc[[-1]])
            logging.info(f"Timestamp of last pushed to dynamoDB         : {df.index[-1]}")
        except Exception as e:
            logging.error(f"Failed to push data to DynamoDB: {e}", exc_info=True)


if __name__ == "__main__":
    main()
