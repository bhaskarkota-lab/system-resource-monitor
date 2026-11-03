from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import psutil, platform, socket, time, threading
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading")

psutil.cpu_percent(None)
for p in psutil.process_iter():
    try: p.cpu_percent(None)
    except: pass

last_net = psutil.net_io_counters()
last_time = time.time()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/system")
def system():
    return jsonify({
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "processor": platform.processor(),
        "cores": psutil.cpu_count(),
        "uptime": int(time.time()-psutil.boot_time())
    })

@app.route("/api/processes")
def processes():
    data=[]
    for p in psutil.process_iter(["pid","name","memory_info"]):
        try:
            data.append({
                "pid":p.info["pid"],
                "name":p.info["name"] or "Unknown",
                "memory":p.info["memory_info"].rss if p.info["memory_info"] else 0,
                "cpu":p.cpu_percent(None),
                "status":p.status()
            })
        except: pass
    return jsonify(data)

@app.route("/api/process/<int:pid>/terminate",methods=["POST"])
def terminate_process(pid):
    try:
        p=psutil.Process(pid)
        p.terminate()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),400

def monitor():
    global last_net,last_time
    while True:
        try:
            now=time.time()
            net=psutil.net_io_counters()
            elapsed=max(now-last_time,.01)
            ram=psutil.virtual_memory()
            disk=psutil.disk_usage("C:\\\\")
            socketio.emit("metrics",{
                "cpu":psutil.cpu_percent(None),
                "cores":psutil.cpu_percent(None,percpu=True),
                "ram":ram.percent,
                "ram_used":ram.used,
                "ram_total":ram.total,
                "available":ram.available,
                "disk":disk.percent,
                "disk_used":disk.used,
                "disk_total":disk.total,
                "down":max(net.bytes_recv-last_net.bytes_recv,0)/elapsed,
                "up":max(net.bytes_sent-last_net.bytes_sent,0)/elapsed,
                "time":datetime.now().strftime("%H:%M:%S")
            })
            last_net,last_time=net,now
        except Exception as e: print(e)
        socketio.sleep(1)

if __name__=="__main__":
    threading.Thread(target=monitor,daemon=True).start()
    print("Advanced Dashboard: http://127.0.0.1:5000")
    socketio.run(app,host="127.0.0.1",port=5000)
