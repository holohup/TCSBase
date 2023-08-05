from collections import OrderedDict
from fastapi import FastAPI
from http import HTTPStatus as status
from pydantic import BaseModel
import redis
import config


r = redis.Redis(
    host=config.redis_host,
    port=config.redis_port,
    db=config.redis_db,
    password=config.redis_password,
)

r.set('foo1', 'bar')
value = r.get('foo1')
print(value)

app = FastAPI(name='TCS assets base')


@app.get('/health')
def health_check():
    return {'message': 'all OK'}


@app.get('/numbers/{number}')
def number_word(number: int):
    return next(
        (asset, result)
        for asset, result in fake_assets.items()
        if asset == str(number)
    )


@app.post('/number/{num}')
def change_number(num: int, new_number: str):
    number = next(n for n in fake_numbers if num in n.keys())
    number[num] = new_number
    return {'status': status.OK, 'data': number}


@app.get('/uids')
def uid_by_ticker(limit: int = 1, offset: int = 1):
    return fake_uids[offset:][:limit]


d = OrderedDict()
d['1'] = '111'
d['0'] = '222'

print(d['0'])
