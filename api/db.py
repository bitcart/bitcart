from gino import Gino

from .settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

db = Gino()

# format from settings
CONNECTION_STR = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
