import json, os, threading, logging
import socketio
from src.vehicle.base_rabbitmq_connection import BaseRabbitMqConnection   # you already have this

class Bridge(BaseRabbitMqConnection):
    """
    • Subscribes to `visor.location` and `visor.distance`
    • Caches the last value per VIN
    • Emits every change to connected browsers via Socket.IO
    """

    def __init__(self, sio: socketio.Server):
        self.sio = sio
        self.exchange       = os.getenv("BROKER_EXCHANGE", "broker")
        self.visor_loc_rk   = os.getenv("VISOR_LOCATION",  "visor.location")
        self.visor_dst_rk   = os.getenv("VISOR_DISTANCE",  "visor.distance")
        self.visor_emb_rk   = os.getenv("VISOR_EMERGENCY_BRAKE", "visor.emergency.brake")
        self.vehicles: dict[str, dict] = {}

        super().__init__(run_retry_queue=False)          # opens conn+chan
        super().run()
        q = self.channel.queue_declare(queue="", exclusive=True).method.queue
        self.channel.exchange_declare(self.exchange, exchange_type="topic", durable=True)
        self.channel.queue_bind(q, self.exchange, self.visor_loc_rk)
        self.channel.queue_bind(q, self.exchange, self.visor_dst_rk)
        self.channel.queue_bind(q, self.exchange, self.visor_emb_rk)

        threading.Thread(target=self._consume, args=(q,), daemon=True).start()
        logging.info("RabbitMQ bridge initialised")

    # ------------------------------------------------------------------
    def _consume(self, queue_name: str):
        self.channel.basic_consume(queue=queue_name, on_message_callback=self._on_msg, auto_ack=True)
        self.channel.start_consuming()

    # ------------------------------------------------------------------
    def _on_msg(self, ch, method, props, body: bytes):
        try:
            data = json.loads(body)
            vin  = data.get("vin") or "<unknown>"
        except Exception:
            return                                              # drop bad payloads

        v = self.vehicles.setdefault(vin, {"vin": vin})

        if method.routing_key == self.visor_loc_rk:
            v["lat"] = data.get("lat")
            v["lon"] = data.get("lon")
        elif method.routing_key == self.visor_dst_rk:                                                   # visor.distance
            v["frontDistance"] = data.get("dst_front")
            v["rearDistance"]  = data.get("dst_back")
        else:
            v["rsn"] = data.get("rsn")
            v["src"] = data.get("src")


        v["time"] = data.get("time")

        if method.routing_key == self.visor_emb_rk:
            self.sio.emit("event", v)
            return

        self.sio.emit("vehicle_update", v)                      # broadcast
