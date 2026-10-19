from flask import Flask, jsonify, render_template
import docker
import psutil
import time
import re

app = Flask(__name__)
client = docker.from_env()
START_TIME = time.time()


def collect_metrics():
    containers = []

    for container in client.containers.list(all=True):
        try:
            container.reload()
            status = container.status
            cpu_percent = 0.0
            memory_percent = 0.0

            if status == "running":
                stats = container.stats(stream=False)
                cpu = stats.get("cpu_stats", {})
                previous = stats.get("precpu_stats", {})

                cpu_delta = (
                    cpu.get("cpu_usage", {}).get("total_usage", 0)
                    - previous.get("cpu_usage", {}).get("total_usage", 0)
                )
                system_delta = (
                    cpu.get("system_cpu_usage", 0)
                    - previous.get("system_cpu_usage", 0)
                )
                online_cpus = cpu.get("online_cpus") or len(
                    cpu.get("cpu_usage", {}).get("percpu_usage", []) or [1]
                )

                if system_delta > 0 and cpu_delta >= 0:
                    cpu_percent = round(
                        cpu_delta / system_delta * online_cpus * 100, 2
                    )

                memory = stats.get("memory_stats", {})
                usage = memory.get("usage", 0)
                limit = memory.get("limit", 0)
                if limit:
                    memory_percent = round(usage / limit * 100, 2)

            containers.append({
                "name": container.name,
                "id": container.short_id,
                "status": status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
            })
        except docker.errors.DockerException:
            continue

    return containers


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/metrics")
def metrics():
    containers = collect_metrics()
    return jsonify({
        "containers": containers,
        "host_cpu_percent": psutil.cpu_percent(interval=0.2),
        "host_memory_percent": psutil.virtual_memory().percent,
        "uptime_seconds": int(time.time() - START_TIME),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    })


@app.route("/api/logs")
def logs():
    result = []
    for container in client.containers.list():
        try:
            lines = container.logs(tail=100, timestamps=True).decode(
                "utf-8", errors="replace"
            ).splitlines()
            for line in lines:
                if re.search(r"\b(error|exception|critical|traceback)\b",
                             line, re.I):
                    result.append({
                        "container": container.name,
                        "message": line[-1000:],
                    })
        except docker.errors.DockerException:
            pass

    return jsonify({"errors": result[-100:]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
