import boto3
import pandas as pd
import numpy as np
from botocore.exceptions import ClientError


def load_df():
    np.random.seed(42)  # Ensures reproducibility
    date_range = pd.date_range(start="2024-01-01", periods=(2*10080), freq="T")  # 2 weeks of minute data

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


def delete_timestream_table(client, database_name, table_name):
    try:
        client.delete_table(DatabaseName=database_name, TableName=table_name)
        print(f"Table '{table_name}' deleted successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Table '{table_name}' does not exist. No need to delete.")
        else:
            print(f"Error deleting table: {e}")


def create_timestream_table(client, database_name, table_name):
    try:
        client.create_table(
            DatabaseName=database_name,
            TableName=table_name,
            RetentionProperties={
                "MemoryStoreRetentionPeriodInHours": 48,
                "MagneticStoreRetentionPeriodInDays": 730
            },
        )
        print(f"Table '{table_name}' created successfully.")
    except ClientError as e:
        print(f"Error creating table: {e}")


def write_records_to_timestream(client, database_name, table_name, df):
    # Ensure all DOUBLE columns have finite values
    df = df.replace([np.inf, -np.inf], np.nan).dropna()

    records = []
    for timestamp, row in df.iterrows():
        # Prepare measures for Timestream
        measures = [
            {"MeasureName": "close", "MeasureValue": str(row["close"]), "MeasureValueType": "DOUBLE"},
            {"MeasureName": "pfma", "MeasureValue": str(row["pfma"]), "MeasureValueType": "DOUBLE"},
            {"MeasureName": "12h_close_mean", "MeasureValue": str(row["12h_close_mean"]), "MeasureValueType": "DOUBLE"},
            {"MeasureName": "desired_op_pct", "MeasureValue": str(row["desired_op_pct"]), "MeasureValueType": "DOUBLE"},
            {"MeasureName": "order_error", "MeasureValue": row["order_error"] if row["order_error"] else "None", "MeasureValueType": "VARCHAR"}
        ]

        for measure in measures:
            record = {
                "Dimensions": [
                    {"Name": "asset", "Value": "BTC/USDT"},
                    {"Name": "exchange", "Value": "Binance"},
                    {"Name": "granularity", "Value": "1m"}
                ],
                "MeasureName": measure["MeasureName"],
                "MeasureValue": measure["MeasureValue"],
                "MeasureValueType": measure["MeasureValueType"],
                "Time": str(int(timestamp.timestamp() * 1000)),  # Use DataFrame index as timestamp in milliseconds
                "TimeUnit": "MILLISECONDS"
            }
            records.append(record)

        # TODO: change this batch logic to handle cases where len(records) may not be exactly 100
        # Write records to Timestream in batches of 100
        if len(records) == 100:
            try:
                client.write_records(DatabaseName=database_name, TableName=table_name, Records=records)
                print("Batch of 100 records written successfully.")
            except ClientError as e:
                print(f"Error writing records: {e}")
            records = []

    # Write remaining records
    if records:
        try:
            client.write_records(DatabaseName=database_name, TableName=table_name, Records=records)
            print("Final batch of records written successfully.")
        except ClientError as e:
            print(f"Error writing final records: {e}")


def main():
    database_name = "my-timestream-database"  # Replace with your Timestream database name
    table_name = "TestTable"  # Replace with your desired table name

    # Initialize boto3 client
    timestream_client = boto3.client("timestream-write", region_name="eu-west-1")  # Replace region if necessary

    # Load the DataFrame
    df = load_df()

    # Delete table if it exists
    delete_timestream_table(timestream_client, database_name, table_name)

    # Create table
    create_timestream_table(timestream_client, database_name, table_name)

    # Enable Magnetic Store Writes
    timestream_client.update_table(
        DatabaseName=database_name,
        TableName=table_name,
        MagneticStoreWriteProperties={
            'EnableMagneticStoreWrites': True
        }
    )

    # Write records to the table
    write_records_to_timestream(timestream_client, database_name, table_name, df)


if __name__ == "__main__":
    main()
