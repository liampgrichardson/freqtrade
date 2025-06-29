from kafka import KafkaConsumer
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

BS = [
    "b-2.freqtrademskcluster.mw89jl.c2.kafka.eu-west-1.amazonaws.com:9098",
    "b-1.freqtrademskcluster.mw89jl.c2.kafka.eu-west-1.amazonaws.com:9098"
]


class MSKTokenProvider:
    def token(self):
        print("Generating MSK IAM token...")
        token, expiration = MSKAuthTokenProvider.generate_auth_token('eu-west-1')
        print("Generated token successfully, expires at:", expiration)
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
    auto_offset_reset='earliest',  # So we get existing messages if not already committed
)

# Print available topics
topics = consumer.topics()
print("Available topics:", topics)

# Start consuming
print(f"Consuming messages from topic: {topic}")
consumer.subscribe([topic])

try:
    for msg in consumer:
        print("Consumed message:", msg.value.decode())
except KeyboardInterrupt:
    print("Stopped consuming.")
finally:
    consumer.close()
    print("Consumer closed.")
