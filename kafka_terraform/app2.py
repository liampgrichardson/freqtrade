from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.admin import NewTopic
import socket
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
import random
import string


BS = ["b-2.freqtrademskcluster.mw89jl.c2.kafka.eu-west-1.amazonaws.com:9098", "b-1.freqtrademskcluster.mw89jl.c2.kafka.eu-west-1.amazonaws.com:9098"]


class MSKTokenProvider:
    def token(self):
        print("Generating MSK IAM token...")
        token, expiration = MSKAuthTokenProvider.generate_auth_token('eu-west-1')
        print("Generated token successfully, expires at:", expiration)
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

# Create the topic if it doesn't exist
admin_client = KafkaAdminClient(
    bootstrap_servers=BS,
    security_protocol='SASL_SSL',
    sasl_mechanism='OAUTHBEARER',
    sasl_oauth_token_provider=tp,
)

try:
    topic_list = [NewTopic(name=topic, num_partitions=1, replication_factor=1)]
    admin_client.create_topics(new_topics=topic_list, validate_only=False)
    print(f"Created topic: {topic}")
except Exception as e:
    print(f"Error creating topic: {e}")

# Produce some random messages
for _ in range(10):
    message = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
    try:
        producer.send(topic, message.encode())
        producer.flush()
        print("Produced message:", message)
    except Exception as e:
        print("Failed to send message:", e)

producer.close()
print("Producer closed.")

# List the topics
consumer = KafkaConsumer(bootstrap_servers=BS,
                         security_protocol='SASL_SSL',
                         sasl_mechanism='OAUTHBEARER',
                         sasl_oauth_token_provider=tp,
                         group_id='my-group')
topics = consumer.topics()
print("Available topics:", topics)

# Consume the messages
print("Consuming messages from topic:", topic)
consumer.subscribe([topic])
for msg in consumer:
    print("Consumed message:", msg.value.decode())

consumer.close()
