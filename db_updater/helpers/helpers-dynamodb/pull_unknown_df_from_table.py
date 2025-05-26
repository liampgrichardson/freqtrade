import boto3
import pandas as pd
from tqdm import tqdm


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


# Parse each item dynamically based on its type
def parse_dynamodb_item(item):
    parsed = {}
    for key, value in item.items():
        # Handle different DynamoDB types
        if 'S' in value:
            parsed[key] = value['S']
        elif 'N' in value:
            parsed[key] = float(value['N'])
        elif 'BOOL' in value:
            parsed[key] = value['BOOL']
        elif 'NULL' in value:
            parsed[key] = None
        elif 'M' in value:
            parsed[key] = value['M']  # Consider parsing nested maps if needed
        elif 'L' in value:
            parsed[key] = value['L']  # Consider parsing nested lists if needed
        else:
            parsed[key] = value  # Fallback
    return parsed


def items_to_df(items):
    if not items:
        return pd.DataFrame()

    print("Example item:", items[-1])

    parsed_items = [parse_dynamodb_item(item) for item in items]
    df = pd.DataFrame(parsed_items)

    # Try to convert 'timestamp' to datetime if it exists
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

    return df


def main():
    timestamps = get_known_timestamps()
    items = fetch_from_dynamodb(timestamps)
    df = items_to_df(items)

    print(f"Total rows fetched: {len(df)}")
    if not df.empty:
        print("\nFirst row:\n", df.iloc[0])
        print("\nLast row:\n", df.iloc[-1])

    # Optionally save to CSV
    # df.to_csv("fetched_data.csv")


if __name__ == "__main__":
    main()
