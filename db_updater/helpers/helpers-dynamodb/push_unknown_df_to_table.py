import boto3
import pandas as pd
import numpy as np
from decimal import Decimal
from tqdm import tqdm
from datetime import datetime, timezone


# Define your load_df function
def load_df():
    np.random.seed(42)  # Ensures reproducibility
    # date_range = pd.date_range(start="2024-01-01", periods=(1 * 10080), freq="T")  # 1 weeks of minute data
    # Get the current UTC time in ISO format
    now_utc = datetime.now(timezone.utc)  # .strftime('%Y-%m-%d %H:%M')
    # Round down to the nearest minute by removing seconds and microseconds
    now_utc = now_utc.replace(second=0, microsecond=0)
    date_range = pd.date_range(end=now_utc, periods=(1 * 10080), freq="T")

    # Generate random close prices between 50000 and 100000
    close_prices = np.random.uniform(50000, 100000, len(date_range))

    # Create a DataFrame
    df = pd.DataFrame({
        "close": close_prices,
        "desired_op_pct": np.random.rand(len(date_range)),  # Simulated percentage data
        "order_error": np.random.choice(["Error A", "Error B", "No error"], size=len(date_range))  # Simulated labels
    }, index=date_range)

    # Compute rolling means
    df['pfma'] = df['close'].rolling(window=60).mean()  # 60-minute rolling mean
    df['12h_close_mean'] = df['close'].rolling(window=720).mean()  # 12-hour rolling mean (720 minutes)

    return df


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
    dynamodb = boto3.resource('dynamodb')
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
    df = load_df()
    push_to_dynamodb(df)


if __name__ == "__main__":
    main()
