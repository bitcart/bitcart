import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"


def when_ready(server):
    from api.logger import get_logger, log_startup_info

    logger = get_logger("startup")
    log_startup_info(logger)
