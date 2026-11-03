import os
import time
import platform
import psutil
import threading

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

app = Flask(__name__)

socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*"
)

# ======================================================
# WINDOWS REMOTE MONITORING CONFIGURATION
# ======================================================

AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")

windows_data = {
    "metrics": None,
    "system": None,
    "processes": [],
    "last_update": None
}

windows_lock = threading.Lock()

# ======================================================
# LOCAL MONITORING
# ======================================================

psutil.cpu_percent(interval=None)
psutil.cpu_percent(percpu=True, interval=None)

previous_network = psutil.net_io_counters()
previous_time = time.time()


def get_metrics():
    global previous_network, previous_time

    cpu = psutil.cpu_percent(interval=None)
    cores = psutil.cpu_percent(percpu=True)

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    current_network = psutil.net_io_counters()
    current_time = time.time()

    elapsed = max(current_time - previous_time, 0.001)

    download = (
        current_network.bytes_recv - previous_network.bytes_recv
    ) / elapsed

    upload = (
        current_network.bytes_sent - previous_network.bytes_sent
    ) / elapsed

    previous_network = current_network
    previous_time = current_time

    return {
        "cpu": cpu,
        "cores": cores,
        "ram": memory.percent,
        "ram_used": memory.used,
        "ram_total": memory.total,
        "available": memory.available,
        "disk": disk.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "down": download,
        "up": upload,
        "time": time.strftime("%H:%M:%S")
    }


def get_system_info():
    return {
        "hostname": platform.node(),
        "os": platform.platform(),
        "processor": platform.processor() or "Unknown",
        "cpu_count": psutil.cpu_count(),
        "uptime": str(
            int(time.time() - psutil.boot_time())
        ) + " seconds"
    }


def get_process_list():
    result = []

    for process in psutil.process_iter(
        ["pid", "name", "memory_info", "cpu_percent", "status"]
    ):
        try:
            info = process.info

            result.append({
                "pid": info["pid"],
                "name": info["name"] or "Unknown",
                "cpu": info["cpu_percent"] or 0,
                "cpu_percent": info["cpu_percent"] or 0,
                "memory": (
                    info["memory_info"].rss / 1024 / 1024
                    if info["memory_info"] else 0
                ),
                "memory_percent": process.memory_percent(),
                "status": info["status"] or "Unknown"
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return result


# ======================================================
# AUTHENTICATION
# ======================================================

def authenticate_agent():
    if not AGENT_TOKEN:
        return False

    supplied_token = request.headers.get("X-Agent-Token", "")

    return supplied_token == AGENT_TOKEN


# ======================================================
# WINDOWS AGENT API
# ======================================================

@app.route("/api/agent/metrics", methods=["POST"])
def receive_windows_metrics():

    if not authenticate_agent():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    with windows_lock:
        windows_data["metrics"] = data
        windows_data["last_update"] = time.time()

    socketio.emit("metrics", data)

    return jsonify({
        "status": "success",
        "message": "Windows metrics received"
    })


@app.route("/api/agent/system", methods=["POST"])
def receive_windows_system():

    if not authenticate_agent():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    with windows_lock:
        windows_data["system"] = data

    return jsonify({"status": "success"})


@app.route("/api/agent/processes", methods=["POST"])
def receive_windows_processes():

    if not authenticate_agent():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, list):
        return jsonify({"error": "Invalid process list"}), 400

    with windows_lock:
        windows_data["processes"] = data

    return jsonify({"status": "success"})


# ======================================================
# DASHBOARD
# ======================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/metrics")
def metrics_api():

    with windows_lock:
        metrics = windows_data["metrics"]
        last_update = windows_data["last_update"]

    if metrics and last_update and time.time() - last_update < 15:
        return jsonify(metrics)

    return jsonify(get_metrics())


@app.route("/api/system")
def system_info():

    with windows_lock:
        system = windows_data["system"]
        last_update = windows_data["last_update"]

    if system and last_update and time.time() - last_update < 15:
        return jsonify(system)

    return jsonify(get_system_info())


@app.route("/api/processes")
def processes():

    with windows_lock:
        process_list = windows_data["processes"]
        last_update = windows_data["last_update"]

    if process_list and last_update and time.time() - last_update < 15:
        return jsonify(process_list)

    return jsonify(get_process_list())


@app.route("/api/process/<int:pid>/terminate", methods=["POST"])
def terminate_process(pid):

    with windows_lock:
        process_list = windows_data["processes"]
        last_update = windows_data["last_update"]

    if process_list and last_update and time.time() - last_update < 15:
        return jsonify({
            "error": "Remote process termination is not enabled yet."
        }), 403

    try:
        process = psutil.Process(pid)
        process.terminate()

        return jsonify({
            "message": "Termination requested"
        })

    except psutil.AccessDenied:
        return jsonify({"error": "Access denied"}), 403

    except psutil.NoSuchProcess:
        return jsonify({"error": "Process not found"}), 404


# ======================================================
# BACKGROUND MONITORING
# ======================================================

def monitoring_loop():

    while True:
        try:
            metrics = get_metrics()
            socketio.emit("metrics", metrics)

        except Exception as error:
            print("Monitoring error:", error)

        socketio.sleep(1)


# ======================================================
# START SERVER
# ======================================================

if __name__ == "__main__":

    socketio.start_background_task(monitoring_loop)

    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
