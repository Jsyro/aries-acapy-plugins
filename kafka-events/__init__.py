"""ACA-Py Event to Kafka Bridge."""

import logging
import re

from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.core.event_bus import Event, EventBus
from aries_cloudagent.core.profile import Profile
from threading import Thread
import asyncio
from .aio_producer import AIOProducer
from .aio_consumer import AIOConsumer

OUTBOUND_PATTERN = "acapy-outbound-.*"
INBOUND_PATTERN = "acapy-inbound-.*"
LOGGER = logging.getLogger(__name__)
TOPICS = []


async def setup(context: InjectionContext):
    """Setup the plugin."""

    plugin_conf = context.settings.get("plugin_config", {}).get("kafka-events", {})
    producer_conf = {}
    consumer_conf = {}
    if plugin_conf:
        producer_conf = plugin_conf.pop("producer-config") or {}
        consumer_conf = plugin_conf.pop("consumer-config") or {}
        producer_conf.update(plugin_conf)
        consumer_conf.update(plugin_conf)

    # Instance the classes
    producer = AIOProducer(producer_conf)
    consumer = AIOConsumer(context, INBOUND_PATTERN, config=consumer_conf)

    # Run the consumer in a thread
    consumer.start_thread()

    # Add the Kafka consumer and producer in the context
    context.injector.bind_instance(AIOConsumer, consumer)
    context.injector.bind_instance(AIOProducer, producer)

    bus = context.inject(EventBus)
    bus.subscribe(re.compile(OUTBOUND_PATTERN), handle_event)


async def teardown(context: InjectionContext):
    consumer = context.inject(AIOConsumer)
    await consumer.stop()


async def handle_event(profile: Profile, event: Event):
    """
    Handle events, passing them off to Kafka.

    Events originating from ACA-Py will be namespaced with `acapy`; for example:

        acapy::record::present_proof::presentation_received

    There are two primary namespaces of ACA-Py events.
    - `record` corresponding to events generated by updates to records. These
      follow the pattern:

        acapy::record::{RECORD_TOPIC}

      This pattern corresponds to records that do not hold a state.
      For stateful records, the following pattern is used:

        acapy::record::{RECORD_TOPIC}::{STATE}

      A majority of records are stateful.
    - `webhook` corresponding to events originally sent only by webhooks or
      that should be sent via webhook. These are emitted by code that has not
      yet been updated to use the event bus. These events should be relatively
      infrequent.
    """
    LOGGER.info("Handling event: %s", event)
    producer = profile.context.inject(AIOProducer)

    await producer.produce(event.topic, event.payload)
