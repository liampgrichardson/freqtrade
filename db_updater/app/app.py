from freqtrade_client import FtRestClient
import boto3
from botocore.exceptions import ClientError
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
pd.set_option('display.max_columns', None)


def main():

    # initialize boto (aws) stuff
    database_name = "my-timestream-database"  # Replace with your Timestream database name
    table_name = "TestTable"  # Replace with your desired table name
    timestream_write_client = boto3.client("timestream-write", region_name="eu-west-1")  # Replace region if necessary
    timestream_query_client = boto3.client("timestream-query", region_name="eu-west-1")

    # Enable Magnetic Store Writes
    timestream_write_client.update_table(
        DatabaseName=database_name,
        TableName=table_name,
        MagneticStoreWriteProperties={
            'EnableMagneticStoreWrites': True
        }
    )

    # initialize freqtrade stuff
    freqtrade_client = FtRestClient("http://127.0.0.1:8080", "freqtrader", "1234")
    strategy = "SampleStrategy"
    pair = "BTC/USDT"
    exchange = "Binance"
    strategy_timeframe = freqtrade_client.strategy(strategy)["timeframe"]

    # Get the status of the bot (should print "pong" if ok)
    print(freqtrade_client.ping())

    while True:
        print("starting loop")

        # get data from freqtrade
        candles = freqtrade_client.pair_candles(pair, strategy_timeframe, 10)

        # Convert the response to a DataFrame
        columns = candles['columns']
        data = candles['data']
        df = pd.DataFrame(data, columns=columns)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # Get last datetime from freqtrade
        last_freqtrade_timestamp = df.index[-1]  # Last index

        # Get last datetime in Timestream
        last_timestream_timestamp = get_last_timestream_timestamp(
            timestream_query_client, database_name, table_name, pair, exchange, strategy_timeframe
        )

        # Log timestamps
        print(f"Last recorded timestamp in Timestream: {last_timestream_timestamp}")
        print(f"Last recorded timestamp from Freqtrade: {last_freqtrade_timestamp}")

        # Wait for new data (not in timestream) to become available
        second_last_freqtrade_timestamp = df.index[-2]
        time_difference = (last_freqtrade_timestamp - second_last_freqtrade_timestamp).total_seconds()
        wait_for_safe_time(last_timestream_timestamp, time_difference)

        # Trim dataframe to data after last Timestream datetime
        # If no last_timestream_timestamp, dont trim dataframe
        if last_timestream_timestamp:
            df = df[df.index > last_timestream_timestamp]
            if df.empty:
                print("No new data to write. Waiting for next cycle...")
                continue  # Skip this iteration

        # Push latest Freqtrade data to Timestream
        write_records_to_timestream(
            timestream_write_client, database_name, table_name, df, strategy_timeframe, pair, exchange
        )


def write_records_to_timestream(client, database_name, table_name, df, strategy_timeframe, pair, exchange):
    records = []

    # Determine column data types dynamically
    for timestamp, row in df.iterrows():
        measures = []

        for col_name, value in row.items():
            # Determine MeasureValueType
            if isinstance(value, (int, float)) and value and not np.isnan(value):
                measure_type = "DOUBLE"
                measure_value = str(value)  # Convert to string for Timestream
            elif isinstance(value, str) and value:
                measure_type = "VARCHAR"
                measure_value = str(value)
            else:
                measure_type = "VARCHAR"
                measure_value = "None"  # Default to "None" for missing/unknown values

            measures.append({
                "MeasureName": col_name,
                "MeasureValue": measure_value,
                "MeasureValueType": measure_type
            })

        # Create records
        for measure in measures:
            record = {
                "Dimensions": [
                    {"Name": "asset", "Value": pair},
                    {"Name": "exchange", "Value": exchange},
                    {"Name": "granularity", "Value": strategy_timeframe}
                ],
                "MeasureName": measure["MeasureName"],
                "MeasureValue": measure["MeasureValue"],
                "MeasureValueType": measure["MeasureValueType"],
                "Time": str(int(timestamp.timestamp() * 1000)),  # Convert timestamp to milliseconds
                "TimeUnit": "MILLISECONDS"
            }
            records.append(record)

            # Write records in batches of 100
            if len(records) == 100:
                try:
                    client.write_records(DatabaseName=database_name, TableName=table_name, Records=records)
                    print("Batch of 100 records written successfully.")
                except ClientError as e:
                    print(f"Error writing records: {e}")
                records = []  # Reset batch

    # Write any remaining records
    if records:
        try:
            client.write_records(DatabaseName=database_name, TableName=table_name, Records=records)
            print("Final batch of records written successfully.")
        except ClientError as e:
            print(f"Error writing final records: {e}")


def get_last_timestream_timestamp(timestream_query_client, database_name, table_name, pair, exchange, strategy_timeframe):
    """
    Query the latest timestamp from Timestream for the given pair, exchange, and strategy timeframe.
    """
    query = f"""
    SELECT MAX(time) AS last_time 
    FROM "{database_name}"."{table_name}"
    WHERE asset = '{pair}' 
      AND exchange = '{exchange}' 
      AND granularity = '{strategy_timeframe}'
    """
    try:
        response = timestream_query_client.query(QueryString=query)

        # Check if there are any rows returned
        if "Rows" in response and response["Rows"]:
            row = response["Rows"][0]["Data"]
            if row:
                # Ensure 'ScalarValue' exists in the response
                last_time = row[0].get("ScalarValue")
                if last_time:
                    return pd.to_datetime(last_time).tz_localize('UTC')
                else:
                    print("No 'ScalarValue' found in the response.")
            else:
                print("No data in the first row of the response.")
        else:
            print("No rows returned from the query.")

    except ClientError as e:
        print(f"Error querying Timestream: {e}")

    return None  # Return None if no data found


def wait_for_safe_time(last_time, time_difference):
    """
    Pauses execution until the current time is at least 5 seconds past the next minute.
    """

    if last_time is None:
        return

    current_time = datetime.now().astimezone()  # Get the current time
    print(f"Current time: {current_time.strftime('%H:%M:%S')}")

    # Calculate the target time (doubled to accommodate for open/close time and
    # extra 5 seconds for data to be surely available)
    time_delay = 2*time_difference
    target_time = last_time.replace(second=0, microsecond=0) + timedelta(seconds=time_delay) + timedelta(seconds=5)

    if target_time > current_time:
        waiting_time = (target_time - current_time).total_seconds()  # Convert timedelta to seconds
        # Log
        print(f"Waiting for {waiting_time} seconds until {target_time.strftime('%H:%M:%S')}.")
        time.sleep(waiting_time)  # Sleep for the calculated time


if __name__ == "__main__":
    main()
