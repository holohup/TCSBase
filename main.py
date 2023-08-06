import asyncio
import logging
import os
import zoneinfo
from datetime import datetime, timedelta
from pickle import dumps, loads
from typing import Union

import redis
import redis.asyncio as a_redis
from dotenv import load_dotenv
from fastapi import FastAPI, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_utils.tasks import repeat_every
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest.retrying.settings import RetryClientSettings
from tinkoff.invest.schemas import Bond, Currency, Etf, Future, Share

MOSCOW_ZONE = zoneinfo.ZoneInfo('Europe/Moscow')
load_dotenv()
r = redis.Redis.from_url(os.getenv('REDIS_URL'))

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG
)
RETRY_SETTINGS = RetryClientSettings(use_retry=True, max_retry_attempt=5)
RO_TOKEN = os.getenv('TCS_RO_TOKEN')
INSTRUMENTS = ('etfs', 'currencies', 'bonds', 'futures', 'shares')

app = FastAPI(name='TCS assets base')


@app.get('/health')
def health_check():
    return {'message': 'all OK'}


@app.get('/ticker/{ticker}', response_class=JSONResponse)
def get_asset_by_ticker(ticker: str, response: Response):
    pickled_asset = r.get(ticker.upper())
    if not pickled_asset:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'message': f'Asset {ticker} not found'}
    asset: Union[Bond, Share, Etf, Future, Currency] = loads(pickled_asset)
    data = jsonable_encoder(asset)
    return data


def asset_filter(asset) -> bool:
    results = (asset.api_trade_available_flag, not asset.blocked_tca_flag)
    return all(results)


async def update():
    assets = []
    logging.info('Preparing to load assets from TCS API')
    async with AsyncRetryingClient(RO_TOKEN, RETRY_SETTINGS) as client:
        for inst in INSTRUMENTS:
            insts = await getattr(client.instruments, inst)()
            assets.extend(insts.instruments)
    filtered = list(filter(asset_filter, assets))
    new_data = {a.ticker: dumps(a) for a in filtered}
    r = a_redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)
    logging.info('Updating the database')
    result = await r.mset(new_data)
    if result is True:
        logging.info('Database update complete successfully')
    all_keys = set(await r.keys())
    deprecated_keys = all_keys - new_data.keys()
    if deprecated_keys:
        logging.warning(f'Deleting deprecated entries: {deprecated_keys}')
        await r.delete(*(key for key in deprecated_keys))
    await r.set('last_updated', datetime.utcnow().isoformat())


def seconds_till_tomorrow_night():
    current_time = datetime.now(MOSCOW_ZONE)
    one_am = (current_time + timedelta(days=1)).replace(
        hour=1, minute=0, second=0
    )
    return (one_am - current_time).seconds


@app.on_event('startup')
@repeat_every(seconds=24 * 60 * 60)
async def update_db_task():
    last_update_time = r.get('last_updated')
    if (
        not last_update_time
        or datetime.fromisoformat(last_update_time.decode()).date()
        < datetime.utcnow().date()
    ):
        await update()
    await asyncio.sleep(seconds_till_tomorrow_night())
    logging.info('Starting scheduled DB Update')
    await update()
    logging.info('DB Update complete')
