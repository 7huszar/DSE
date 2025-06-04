import json
import queue
import threading
import time
import pika
import os
import logging
from pika.exceptions import AMQPConnectionError, AMQPChannelError


class BaseRabbitMqConnection:

    def __init__(self, run_retry_queue: bool):
        self.connection = None
        self.channel = None
        self.connection_dead = threading.Condition()
        self.retry_queue = queue.Queue()

        self.RABBITMQ_USER = os.environ['RABBITMQ_USER']
        self.RABBITMQ_PWD = os.environ['RABBITMQ_PASSWORD']
        self.RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
        self.RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
        self.RETRY_WAIT = int(os.getenv("RETRY_WAIT", 5))

        self.run_retry_queue: bool = run_retry_queue

        self.credentials = pika.PlainCredentials(
            username=self.RABBITMQ_USER,
            password=self.RABBITMQ_PWD
        )

        self.logger = logging.getLogger(self.__class__.__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        )

    def get_rabbitmq_connection(self):
        return pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.RABBITMQ_HOST,
                port=self.RABBITMQ_PORT,
                credentials=self.credentials
            )
        )

    def establish_connection(self):
        not_succeeded = True
        if self.connection is not None and not self.connection.is_closed:
            return

        while not_succeeded:
            try:
                self.connection = self.get_rabbitmq_connection()
                not_succeeded = False
            except AMQPConnectionError as e:
                self.logger.warning(f"Failed to establish connection: {repr(e)}. Retrying in {self.RETRY_WAIT} seconds.")
                time.sleep(self.RETRY_WAIT)

        self.logger.info("Successfully established connection to RabbitMQ.")

    def open_channel(self):
        not_succeeded = True

        if self.connection is None or self.connection.is_closed:
            self.establish_connection()

        while not_succeeded:
            try:
                self.channel = self.connection.channel()
                not_succeeded = False
            except AMQPConnectionError as e:
                self.logger.warning(f"Failed to open channel: {repr(e)}")
                self.establish_connection()
            except AMQPChannelError as e:
                self.logger.warning(f"Failed to open channel: {repr(e)}")

        self.logger.info("Successfully opened RabbitMQ channel.")

    def declare_channels(self):
        logging.info("no channels implemented")
        # do nothing, if not implemented

    def reestablish_connection(self):
        while True:
            with self.connection_dead:
                self.connection_dead.wait()
            self.establish_connection()
            self.open_channel()

    def get_retry_routing_key(self):
        raise NotImplementedError("Subclass must implement get_retry_routing_key")


    def process_failed_msg(self):
        while True:
            with self.retry_queue.not_empty:
                while self.retry_queue.empty():
                    self.retry_queue.not_empty.wait()
            if self.channel.is_closed or self.connection.is_closed:
                with self.connection_dead:
                    self.connection_dead.notify_all()
                time.sleep(self.RETRY_WAIT)
                continue
            self.logger.info("Try to resend all failed msg.")
            while not self.retry_queue.empty():
                pkg = self.retry_queue.get()
                try:
                    self.channel.basic_publish(
                        exchange='broker',
                        routing_key=self.get_retry_routing_key(),
                        body=json.dumps(pkg).encode("utf-8")
                    )
                except (AMQPChannelError, AMQPConnectionError) as e:
                    self.logger.warning(f"Failed to resend msg: {repr(e)}")
                    with self.connection_dead:
                        self.connection_dead.notify_all()
                    self.retry_queue.put(pkg)
                    break

    def run(self):
        self.establish_connection()
        self.open_channel()

        if self.run_retry_queue:
            threading.Thread(target=self.process_failed_msg, daemon=True).start()

    def get_env_variables(self):
        return (f"RABBITMQ_USER: {self.RABBITMQ_USER}, "
                f"RABBITMQ_PWD: *, "
                f"RABBITMQ_PORT: {self.RABBITMQ_PORT}, "
                f"RETRY_WAIT: {self.RETRY_WAIT}")

    def log_stats(self):
        self.logger.info(f"Started {self.__class__.__name__} with: {self.get_env_variables()}")