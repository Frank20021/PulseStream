from shared.config import Settings


def kafka_client_kwargs(settings: Settings) -> dict:
    kwargs: dict = {"bootstrap_servers": settings.kafka_bootstrap_servers}
    protocol = settings.kafka_security_protocol.upper()
    if protocol != "PLAINTEXT":
        kwargs["security_protocol"] = protocol
        if settings.kafka_sasl_mechanism:
            kwargs["sasl_mechanism"] = settings.kafka_sasl_mechanism
            kwargs["sasl_plain_username"] = settings.kafka_sasl_username or ""
            kwargs["sasl_plain_password"] = settings.kafka_sasl_password or ""
    return kwargs
