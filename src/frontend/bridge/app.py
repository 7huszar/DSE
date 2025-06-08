"""
Flask + Flask-SocketIO server that
1. exposes /api/vehicles  (initial page load)
2. pushes every RabbitMQ message to browsers via Socket.IO
"""

import logging
from flask import Flask
from flask_socketio import SocketIO
from rabbitmq_bridge import Bridge          # local module in the same folder

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")    # WebSocket endpoint


# Start the RabbitMQ → Socket.IO bridge *inside* the same process
bridge = Bridge(socketio)

if __name__ == "__main__":                              # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    socketio.run(app, host="0.0.0.0", port=8080, use_reloader=False, allow_unsafe_werkzeug=True)
