import logging
from freqtrade_client import FtRestClient
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import json
from kafka import KafkaProducer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

topicname = 'freqtrade-candles'

BROKERS = 'boot-gfwyfklm.c3.kafka-serverless.eu-west-1.amazonaws.com:9098'
region = 'eu-west-1'

class MSKTokenProvider:
    @staticmethod
    def token():
        token, _ = MSKAuthTokenProvider.generate_auth_token(region)
        return token


tp = MSKTokenProvider()

producer = KafkaProducer(
    bootstrap_servers=BROKERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    retry_backoff_ms=500,
    request_timeout_ms=20000,
    security_protocol='SASL_SSL',
    sasl_mechanism='OAUTHBEARER',
    sasl_oauth_token_provider=tp)


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


def send_to_kafka(df_row):
    """
    Send a single DataFrame row to Kafka as JSON
    """
    record = df_row.to_dict(orient='records')[0]  # convert single row to dict
    producer.send(topicname, value=record)
    producer.flush()


def main():
    freqtrade_client = FtRestClient("http://127.0.0.1:8080", "freqtrader", "1234")
    strategy = "SampleStrategy"
    strategy_timeframe = freqtrade_client.strategy(strategy)["timeframe"]
    pair = "BTC/USDT"

    logging.info(freqtrade_client.ping())

    candles = None
    while candles is None:
        try:
            candles = freqtrade_client.pair_candles(pair, strategy_timeframe, 10)
        except Exception as e:
            logging.error(f"Failed to fetch candles: \n{e}", exc_info=True)
            time.sleep(5)

    while True:
        logging.info("Starting loop")

        try:
            candles = freqtrade_client.pair_candles(pair, strategy_timeframe, 10)
            columns = candles['columns']
            data = candles['data']
            df = pd.DataFrame(data, columns=columns)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            last_freqtrade_timestamp = df.index[-1]
            scd_last_freqtrade_timestamp = df.index[-2]

            send_to_kafka(df.iloc[[-1]])
            logging.info(f"Timestamp of last sent to Kafka: {df.index[-1]}")

            sleep_until_target_time(scd_last_freqtrade_timestamp, last_freqtrade_timestamp)

        except Exception as e:
            logging.error(f"Failed to fetch or format candles or send data: \n{e}", exc_info=True)
            time.sleep(5)
            continue


if __name__ == "__main__":
    main()
