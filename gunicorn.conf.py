import multiprocessing
import os
import shutil
import tempfile

from uvicorn.workers import UvicornWorker


class CustomUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"ws": "websockets-sansio"}


bind = "0.0.0.0:8000"
workers = os.environ.get("BITCART_API_WORKERS") or multiprocessing.cpu_count() * 2 + 1
worker_class = CustomUvicornWorker

os.environ["BITCART_ENV"] = "production"

prometheus_multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR") or tempfile.mkdtemp(prefix="prometheus_multiproc_")
if os.path.exists(prometheus_multiproc_dir):
    shutil.rmtree(prometheus_multiproc_dir)
os.makedirs(prometheus_multiproc_dir, exist_ok=True)
os.environ["PROMETHEUS_MULTIPROC_DIR"] = prometheus_multiproc_dir

from prometheus_client import multiprocess  # noqa: E402 # it uses PROMETHEUS_MULTIPROC_DIR


def child_exit(server, worker):  # type: ignore
    multiprocess.mark_process_dead(worker.pid)


def on_exit(server):  # type: ignore
    if os.path.exists(prometheus_multiproc_dir):
        shutil.rmtree(prometheus_multiproc_dir)
