# -*- coding: utf-8 -*-

from cloudbrain.settings import RABBITMQ_ADDRESS

import pika
import json
import logging

from sockjs.tornado.conn import SockJSConnection
from sockjs.tornado import SockJSRouter
from tornado.ioloop import PeriodicCallback, IOLoop
from tornado.web import RequestHandler, Application

from cloudbrain.subscribers.SubscriberInterface import Subscriber

SERVER_PORT = 31415
logging.getLogger().setLevel(logging.INFO)



class RtStreamConnection(SockJSConnection):
    """RtStreamConnection connection implementation"""
    # Class level variable
    clients = set()

    def __init__(self, session):
        super(self.__class__, self).__init__(session)
        self.subscribers = {}


    def send_probe_factory(self, metric_name):

        def send_probe(body):
            logging.debug("GOT: " + body)
            buffer_content = json.loads(body)

            for record in buffer_content:
                record["metric"] = metric_name
                self.send(json.dumps(record))

        return send_probe


    def on_open(self, info):
        logging.info("Got a new connection...")
        self.clients.add(self)
        # self.timeout = PeriodicCallback(self.send_heartbeat, 1000)
        # self.timeout.start()

    # This will receive instructions from the client to change the
    # stream. After the connection is established we expect to receive a JSON
    # with deviceName, deviceId, metric; then we subscribe to RabbitMQ and
    # start streaming the data.
    #
    # NOTE: it's not possible to open multiple connections from the same client.
    #       so in case we need to stream different devices/metrics/etc. at the
    #       same time, we need to use a solution that is like the multiplexing
    #       in the sockjs-tornado examples folder.
    def on_message(self, message):
        logging.info("Got a new message: " + message)

        stream_configuration = json.loads(message)
        device_name = stream_configuration['deviceName']
        device_id = stream_configuration['deviceId']
        metric = stream_configuration['metric']

        if metric not in self.subscribers:
            self.subscribers[metric] = TornadoSubscriber(callback=self.send_probe_factory(metric),
                                       device_name=device_name,
                                       device_id=device_id,
                                       rabbitmq_address=RABBITMQ_ADDRESS,
                                       metric_name=metric)


            self.subscribers[metric].connect()



    def on_close(self):
        for (metric, subscriber) in self.subscribers.keys():
          if subscriber is not None:
              subscriber.disconnect()

        self.subscribers = {}
        #self.timeout.stop()
        self.clients.remove(self)

    def send_heartbeat(self):
        self.broadcast(self.clients, 'message')


class MockHandler(RequestHandler):
    """Just a mock page to test it out..."""
    def get(self):
        self.render('mock.html')

class WebWorkerHandler(RequestHandler):
    """
    Just a custom handler for the web-worker... please we need to replace
    this stuff with a proper router :)
    """
    def get(self):
        self.render('live-data-worker.js')

# Based on: https://pika.readthedocs.org/en/0.9.14/examples/tornado_consumer.html
class TornadoSubscriber(object):

    QUEUE = 'test'

    def __init__(self, callback, device_name, device_id, rabbitmq_address, metric_name):
        self.callback = callback
        self.device_name = device_name
        self.device_id = device_id
        self.metric_name = metric_name

        self.connection = None
        self.channel = None

        self.host = RABBITMQ_ADDRESS
        self.queue_name = None


    def connect(self):
        credentials = pika.PlainCredentials('cloudbrain', 'cloudbrain')
        self.connection = pika.adapters.tornado_connection.TornadoConnection(pika.ConnectionParameters(
                                        host=self.host, credentials=credentials),
                                        self.on_connected,
                                        stop_ioloop_on_close=False,
                                        custom_ioloop=IOLoop.instance())

    def disconnect(self):
        if self.connection is not None:
            self.connection.close()

    def on_connected(self, connection):
        self.connection = connection
        self.connection.add_on_close_callback(self.on_connection_closed)
        self.open_channel()

    def on_connection_closed(self, connection, reply_code, reply_text):
        self.connection = None
        self.channel = None

    def open_channel(self):
        self.connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        self.channel = channel
        self.channel.add_on_close_callback(self.on_channel_closed)
        # self.setup_exchange(self.EXCHANGE)
        # self.channel.confirm_delivery(self.on_delivery_confirmation)
        key = "%s:%s:%s" % (self.device_id, self.device_name, self.metric_name)
        self.channel.exchange_declare(self.on_exchange_declareok,
                                      exchange=key,
                                      type='direct')
        # self.queue_name = self.channel.queue_declare(exclusive=True).method.queue

    def on_channel_closed(self, channel, reply_code, reply_text):
        self.connection.close()

    def on_exchange_declareok(self, unused_frame):
        self.channel.queue_declare(self.on_queue_declareok, self.QUEUE)

    def on_queue_declareok(self, unused_frame):
        key = "%s:%s:%s" %(self.device_id,self.device_name, self.metric_name)
        self.channel.queue_bind(
                       self.on_bindok,
                       exchange=key,
                       queue=self.QUEUE,
                       routing_key=key)

    def on_bindok(self, unused_frame):
        self.channel.add_on_cancel_callback(self.on_consumer_cancelled)
        self.consumer_tag = self.channel.basic_consume(self.on_message, self.QUEUE)

    def on_consumer_cancelled(self, method_frame):
        if self.channel:
            self.channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        self.acknowledge_message(basic_deliver.delivery_tag)
        self.callback(body)

    def acknowledge_message(self, delivery_tag):
        self.channel.basic_ack(delivery_tag)

if __name__ == "__main__":

    # 1. Create chat router
    RtStreamRouter = SockJSRouter(RtStreamConnection, '/rt-stream')

    # 2. Create Tornado application
    app = Application(
            [(r"/", MockHandler), (r"/live-data-worker.js", WebWorkerHandler)] + RtStreamRouter.urls
    )

    # 3. Make Tornado app listen on Pi
    app.listen(SERVER_PORT)

    print "Real-time data server running at http://localhost:%s" %SERVER_PORT

    # 4. Start IOLoop
    IOLoop.instance().start()


