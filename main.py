from collections import OrderedDict
from fastapi import FastAPI
from http import HTTPStatus as status
# from tinkoff.invest.schemas import Share, Future
import redis
import config
# from json import loads
from dotenv import load_dotenv
import os
from pickle import loads
# from tinkoff.invest import utils

load_dotenv()
r = redis.Redis.from_url(os.getenv('REDIS_URL'))

value = r.get('MXU3')
# print(value)
# print(type(loads(value))) #dict
print(loads(value))
print(type(loads(value)))
# print(value)

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
