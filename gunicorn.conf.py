import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = os.environ.get("BITCART_API_WORKERS") or multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
