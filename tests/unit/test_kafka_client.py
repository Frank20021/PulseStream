from shared.config.settings import Settings
from shared.kafka.client import kafka_client_kwargs


def test_kafka_client_stays_plaintext_locally() -> None:
    settings = Settings(kafka_bootstrap_servers="kafka:9092")
    assert kafka_client_kwargs(settings) == {"bootstrap_servers": "kafka:9092"}


def test_kafka_client_adds_sasl_for_managed_clusters() -> None:
    settings = Settings(
        kafka_bootstrap_servers="boot.example:9092",
        kafka_security_protocol="SASL_SSL",
        kafka_sasl_mechanism="PLAIN",
        kafka_sasl_username="key",
        kafka_sasl_password="secret",
    )
    kwargs = kafka_client_kwargs(settings)
    assert kwargs["security_protocol"] == "SASL_SSL"
    assert kwargs["sasl_mechanism"] == "PLAIN"
    assert kwargs["sasl_plain_username"] == "key"
