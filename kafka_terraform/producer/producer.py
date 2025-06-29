import logging
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
import socket
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
import time
import random
import string

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

producer = KafkaProducer(
    bootstrap_servers=BS,
    security_protocol='SASL_SSL',
    sasl_mechanism='OAUTHBEARER',
    sasl_oauth_token_provider=tp,
    client_id=socket.gethostname(),
)

topic = "test-topic"

admin_client = KafkaAdminClient(
    bootstrap_servers=BS,
    security_protocol='SASL_SSL',
    sasl_mechanism='OAUTHBEARER',
    sasl_oauth_token_provider=tp,
)

try:
    topic_list = [NewTopic(name=topic, num_partitions=1, replication_factor=1)]
    admin_client.create_topics(new_topics=topic_list, validate_only=False)
    logger.info(f"Created topic: {topic}")
except Exception as e:
    logger.warning(f"Error creating topic: {e}")

start_time = time.time()
duration = 120  # Run duration in seconds

while time.time() - start_time < duration:
    message = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
    try:
        producer.send(topic, message.encode())
        producer.flush()
        logger.info(f"Produced message: {message}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
    time.sleep(2)

producer.close()
logger.info("Producer closed.")
