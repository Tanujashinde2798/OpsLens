import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "opslens_main",
    Path(__file__).resolve().parents[1] / "app.py",
)
import sys

opslens = importlib.util.module_from_spec(spec)
sys.modules["opslens_main"] = opslens
spec.loader.exec_module(opslens)


def test_dashboard_returns_success():
    client = opslens.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"html" in response.data.lower()


@patch("opslens_main.collect_metrics", return_value=[])
@patch("opslens_main.psutil.cpu_percent", return_value=15.0)
@patch(
    "opslens_main.psutil.virtual_memory",
    return_value=SimpleNamespace(percent=40.0),
)
def test_metrics_endpoint_returns_expected_data(
    mock_memory, mock_cpu, mock_containers
):
    client = opslens.app.test_client()

    response = client.get("/api/metrics")

    assert response.status_code == 200
    data = response.get_json()
    assert data["containers"] == []
    assert data["host_cpu_percent"] == 15.0
    assert data["host_memory_percent"] == 40.0
    assert "uptime_seconds" in data
    assert "timestamp" in data


@patch("opslens_main.client.containers.list", return_value=[])
def test_logs_endpoint_returns_empty_errors(mock_containers):
    client = opslens.app.test_client()

    response = client.get("/api/logs")

    assert response.status_code == 200
    assert response.get_json() == {"errors": []}
