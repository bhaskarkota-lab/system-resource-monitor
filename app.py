import os
import time
import platform
import psutil

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

app = Flask(__name__)

socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*"
)

# Initialize CPU measurement
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/system")
def system_info():
    return jsonify({
        "hostname": platform.node(),
        "os": platform.platform(),
        "processor": platform.processor() or "Unknown",
        "cpu_count": psutil.cpu_count(),
        "uptime": str(
            int(time.time() - psutil.boot_time())
        ) + " seconds"
    })


@app.route("/api/processes")
def processes():
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
                "memory": (
                    info["memory_info"].rss / 1024 / 1024
                    if info["memory_info"] else 0
                ),
                "status": info["status"] or "Unknown"
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return jsonify(result)


@app.route("/api/process/<int:pid>/terminate", methods=["POST"])
def terminate_process(pid):
    try:
        process = psutil.Process(pid)
        process.terminate()

        return jsonify({
            "message": "Termination requested"
        })

    except psutil.AccessDenied:
        return jsonify({
            "error": "Access denied"
        }), 403

    except psutil.NoSuchProcess:
        return jsonify({
            "error": "Process not found"
        }), 404


def monitoring_loop():
    while True:
        try:
            metrics = get_metrics()
            socketio.emit("metrics", metrics)
        except Exception as error:
            print("Monitoring error:", error)

        socketio.sleep(1)


if __name__ == "__main__":
    socketio.start_background_task(monitoring_loop)

    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
