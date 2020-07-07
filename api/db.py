from gino import Gino

from .settings import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

db = Gino(
    naming_convention={
        "ix": "%(column_0_label)s_idx",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
        "fk": "%(table_name)s_%(column_0_name)s_%(referred_table_name)s_fkey",
        "pk": "%(table_name)s_pkey",
    }
)

# format from settings
CONNECTION_STR = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
