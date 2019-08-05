import fastapi
from gino import Gino

db = Gino()

CONNECTION_STR = 'postgresql://postgres:123@@localhost/gino'
