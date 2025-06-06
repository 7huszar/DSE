"""
Flask + Flask-SocketIO server that
1. exposes /api/vehicles  (initial page load)
2. pushes every RabbitMQ message to browsers via Socket.IO
"""

import os, logging
from flask import Flask, jsonify
from flask_socketio import SocketIO
from rabbitmq_bridge import Bridge          # local module in the same folder

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")    # WebSocket endpoint

# ----------------------------------------------------------------------
# REST bootstrap – the Vue front-end calls this once right after page load
@app.route("/api/vehicles")
def vehicles():
    return jsonify(list(bridge.vehicles.values()))

# ----------------------------------------------------------------------
# Start the RabbitMQ → Socket.IO bridge *inside* the same process
bridge = Bridge(socketio)

if __name__ == "__main__":                              # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    socketio.run(app, host="0.0.0.0", port=80, use_reloader=False)
