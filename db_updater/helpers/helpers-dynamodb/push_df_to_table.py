import boto3
import pandas as pd
import numpy as np
from decimal import Decimal
from tqdm import tqdm


# Define your load_df function
def load_df():
    np.random.seed(42)  # Ensures reproducibility
    date_range = pd.date_range(start="2024-01-01", periods=(1 * 10080), freq="T")  # 1 weeks of minute data

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


# Push the data to DynamoDB
def push_to_dynamodb(df):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TradingApp-table1')

    with table.batch_writer() as batch:
        for index, row in tqdm(df.iterrows(), total=len(df), desc="Uploading to DynamoDB"):
            item = {
                'TradingApp-table1-partitionkey': str(index),
                'timestamp': str(index),
                'close': Decimal(str(row['close'])),
                'desired_op_pct': Decimal(str(row['desired_op_pct'])),
                'order_error': row['order_error'],
            }
            batch.put_item(Item=item)


def main():
    df = load_df()
    push_to_dynamodb(df)


if __name__ == "__main__":
    main()
