import json
import logging
import uuid
from concurrent.futures import TimeoutError
import google.api_core.exceptions
from google.api_core import retry
from google.cloud import pubsub_v1

from octue.mixins import CoolNameable


logger = logging.getLogger(__name__)


OCTUE_NAMESPACE = "octue.services"
ANSWERS_NAMESPACE = "answers"


# Switch message batching off by setting max_messages to 1. This minimises latency and is recommended for
# microservices publishing single messages in a request-response sequence.
BATCH_SETTINGS = pubsub_v1.types.BatchSettings(max_bytes=10 * 1000 * 1000, max_latency=0.01, max_messages=1)


class Topic:
    def __init__(self, name, gcp_project_name, service):
        self.name = name
        self.service = service
        self.path = self.service._publisher.topic_path(gcp_project_name, f"{OCTUE_NAMESPACE}.{self.name}")

    def create(self, allow_existing=False):
        if not allow_existing:
            self.service._publisher.create_topic(name=self.path)
            self._log_creation()
            return

        try:
            self.service._publisher.create_topic(name=self.path)
        except google.api_core.exceptions.AlreadyExists:
            pass
        self._log_creation()

    def delete(self):
        self.service._publisher.delete_topic(topic=self.path)
        logger.debug("%r deleted topic %r.", self.service, self.path)

    def _log_creation(self):
        logger.debug("%r created topic %r.", self.service, self.path)


class Subscription:
    def __init__(self, name, topic, gcp_project_name, service):
        self.name = name
        self.topic = topic
        self.service = service
        self.path = self.service._subscriber.subscription_path(gcp_project_name, f"{OCTUE_NAMESPACE}.{self.name}")

    def create(self, allow_existing=False):
        if not allow_existing:
            self.service._subscriber.create_subscription(topic=self.topic.path, name=self.path)
            self._log_creation()
            return

        try:
            self.service._subscriber.create_subscription(topic=self.topic.path, name=self.path)
        except google.api_core.exceptions.AlreadyExists:
            pass
        self._log_creation()

    def delete(self):
        self.service._subscriber.delete_subscription(subscription=self.path)
        logger.debug("%r deleted subscription %r.", self.service, self.path)

    def _log_creation(self):
        logger.debug("%r created subscription %r.", self.service, self.path)


class Service(CoolNameable):
    def __init__(self, name, gcp_project_name, id=None, run_function=None):
        self.name = name
        self.id = id
        self.gcp_project_name = gcp_project_name
        self.run_function = run_function
        self._publisher = pubsub_v1.PublisherClient(BATCH_SETTINGS)
        self._subscriber = pubsub_v1.SubscriberClient()
        super().__init__()

    def __repr__(self):
        return f"<{type(self).__name__}({self.cool_name!r})>"

    def serve(self, timeout=None):
        topic = Topic(name=self.id, gcp_project_name=self.gcp_project_name, service=self)
        topic.create(allow_existing=True)

        subscription = Subscription(name=self.id, topic=topic, gcp_project_name=self.gcp_project_name, service=self)
        subscription.create(allow_existing=True)

        future = self._subscriber.subscribe(subscription=subscription.path, callback=self.answer)
        logger.debug("%r is waiting for questions.", self)

        with self._subscriber:
            try:
                future.result(timeout=timeout)
            except TimeoutError:
                future.cancel()

    def answer(self, question):
        logger.info("%r received a question.", self)
        data = json.loads(question.data.decode())
        question_uuid = question.attributes["question_uuid"]
        question.ack()

        output_values = self.run_function(data).output_values

        topic = Topic(
            name=".".join((self.id, ANSWERS_NAMESPACE, question_uuid)),
            gcp_project_name=self.gcp_project_name,
            service=self,
        )
        self._publisher.publish(topic=topic.path, data=json.dumps(output_values).encode())
        logger.info("%r responded on topic %r.", self, topic.path)

    def ask(self, service_id, input_values, input_manifest=None):
        question_uuid = str(int(uuid.uuid4()))

        response_topic_and_subscription_name = ".".join((service_id, ANSWERS_NAMESPACE, question_uuid))
        response_topic = Topic(
            name=response_topic_and_subscription_name, gcp_project_name=self.gcp_project_name, service=self
        )
        response_topic.create(allow_existing=False)

        response_subscription = Subscription(
            name=response_topic_and_subscription_name,
            topic=response_topic,
            gcp_project_name=self.gcp_project_name,
            service=self,
        )
        response_subscription.create(allow_existing=False)

        question_topic = Topic(name=service_id, gcp_project_name=self.gcp_project_name, service=self)
        future = self._publisher.publish(
            topic=question_topic.path, data=json.dumps(input_values).encode(), question_uuid=question_uuid
        )
        future.result()

        logger.debug("%r asked question to %r service. Question UUID is %r.", self, service_id, question_uuid)
        return response_subscription

    def wait_for_answer(self, subscription, timeout=20):
        answer = self._subscriber.pull(
            request={"subscription": subscription.path, "max_messages": 1}, retry=retry.Retry(deadline=timeout),
        ).received_messages[0]

        self._subscriber.acknowledge(request={"subscription": subscription.path, "ack_ids": [answer.ack_id]})
        logger.debug("%r received a response to question on topic %r", self, subscription.topic.path)

        subscription.delete()
        subscription.topic.delete()
        return json.loads(answer.message.data.decode())
