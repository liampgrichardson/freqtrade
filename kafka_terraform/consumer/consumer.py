import logging
from kafka import KafkaConsumer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

BS = [
    "b-2.freqtrademskcluster.mw89jl.c2.kafka.eu-west-1.amazonaws.com:9098",
    "b-1.freqtrademskcluster.mw89jl.c2.kafka.eu-west-1.amazonaws.com:9098"
]


class MSKTokenProvider:
    def token(self):
        logger.info("Generating MSK IAM token...")
        token, expiration = MSKAuthTokenProvider.generate_auth_token('eu-west-1')
        logger.info(f"Generated token successfully, expires at: {expiration}")
        return token


tp = MSKTokenProvider()

topic = "test-topic"

# Initialize consumer
consumer = KafkaConsumer(
    bootstrap_servers=BS,
    security_protocol='SASL_SSL',
    sasl_mechanism='OAUTHBEARER',
    sasl_oauth_token_provider=tp,
    group_id='my-group',
    auto_offset_reset='earliest',
)

# Log available topics
topics = consumer.topics()
logger.info(f"Available topics: {topics}")

# Start consuming
logger.info(f"Consuming messages from topic: {topic}")
consumer.subscribe([topic])

try:
    for msg in consumer:
        logger.info(f"Consumed message: {msg.value.decode()}")
except KeyboardInterrupt:
    logger.info("Stopped consuming due to keyboard interrupt.")
except Exception as e:
    logger.error(f"Error while consuming messages: {e}")
finally:
    consumer.close()
    logger.info("Consumer closed.")
