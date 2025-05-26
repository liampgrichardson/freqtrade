import boto3
import pandas as pd
from tqdm import tqdm
from decimal import Decimal


# Define your known timestamps
def get_known_timestamps():
    return pd.date_range(start="2024-01-01", periods=1440, freq="T")


# Batch fetch data from DynamoDB using the client
def fetch_from_dynamodb(timestamps):
    dynamodb = boto3.client('dynamodb')
    table_name = 'TradingApp-table1'

    batch_size = 100  # Max allowed by DynamoDB
    all_items = []

    for i in tqdm(range(0, len(timestamps), batch_size), desc="Batch fetching"):
        batch_keys = [{'TradingApp-table1-partitionkey': {'S': str(ts)}} for ts in timestamps[i:i + batch_size]]
        request = {table_name: {'Keys': batch_keys}}

        # Handle retries for unprocessed keys
        while request:
            response = dynamodb.batch_get_item(RequestItems=request)
            all_items.extend(response.get('Responses', {}).get(table_name, []))
            request = response.get('UnprocessedKeys', {})
            if request:
                print("need to handle UnprocessedKeys")

    return all_items


def items_to_df(items):
    if not items:
        return pd.DataFrame()

    print(items[-1])
    # Unpack DynamoDB raw format directly
    parsed_items = [{
        'timestamp': item['timestamp']['S'],
        'close': float(item['close']['N']),
        'desired_op_pct': float(item['desired_op_pct']['N']),
        'order_error': item['order_error']['S']
    } for item in items]

    df = pd.DataFrame(parsed_items)

    # Convert timestamp to datetime and set index
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)

    return df


def main():
    timestamps = get_known_timestamps()
    items = fetch_from_dynamodb(timestamps)
    df = items_to_df(items)

    # Sort by timestamp index (just in case)
    df.sort_index(inplace=True)

    # Print results
    print(f"Total rows fetched: {len(df)}")
    print("\nFirst row:\n", df.iloc[0])
    print("\nLast row:\n", df.iloc[-1])

    # df.to_csv("fetched_data.csv")


if __name__ == "__main__":
    main()
