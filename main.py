import asyncio
import logging
import os
import zoneinfo
from datetime import datetime, timedelta
from pickle import dumps

import redis.asyncio as a_redis
from dotenv import load_dotenv
from fastapi import FastAPI, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_utils.tasks import repeat_every
from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest.retrying.settings import RetryClientSettings

from repo import TCSAssetRepo

MOSCOW_ZONE = zoneinfo.ZoneInfo('Europe/Moscow')
load_dotenv()


logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG
)
RETRY_SETTINGS = RetryClientSettings(use_retry=True, max_retry_attempt=5)
RO_TOKEN = os.getenv('TCS_RO_TOKEN')
INSTRUMENTS = ('etfs', 'currencies', 'bonds', 'futures', 'shares')
REPO = TCSAssetRepo()
app = FastAPI(name='TCS assets base')
R = a_redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)


@app.get('/health')
def health_check():
    return {'message': 'all OK'}


# asset_id - ticker or uid
@app.get('/asset/{asset_id}', response_class=JSONResponse)
def get_asset_by_ticker(asset_id: str, response: Response):
    asset = REPO[asset_id]
    if not asset:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'message': f'Asset {asset_id} not found'}
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
    new_data = {a.ticker.upper(): dumps(a) for a in filtered}
    new_data.update({a.uid.upper(): dumps(a) for a in filtered})
    logging.info('Updating the database')
    async with R as client:
        result = await client.mset(new_data)
        if result is True:
            logging.info('Database update complete successfully')
        all_keys = set(await client.keys())
        deprecated_keys = all_keys - new_data.keys()
        if deprecated_keys:
            logging.warning(f'Deleting deprecated entries: {deprecated_keys}')
            await client.delete(*(key for key in deprecated_keys))
        update_time = datetime.utcnow().isoformat()
        await client.set('last_updated', update_time)
        logging.info(f'Update last_updated time to {update_time}')


def seconds_till_tomorrow_night():
    current_time = datetime.now(MOSCOW_ZONE)
    one_am = (current_time + timedelta(days=1)).replace(
        hour=1, minute=0, second=0
    )
    return (one_am - current_time).seconds


@app.on_event('startup')
@repeat_every(seconds=10)
async def update_db_task():
    logging.info('Starting scheduled DB Update')
    async with R as client:
        last_update_time = await client.get('last_updated')
    if (
        not last_update_time
        or datetime.fromisoformat(last_update_time).date()
        < datetime.utcnow().date()
    ):
        await update()
    sleep_seconds = seconds_till_tomorrow_night()
    logging.info(f'Sleeping {sleep_seconds // 60} minutes till next db update.')
    await asyncio.sleep(sleep_seconds)
    await update()
    logging.info('DB Update complete')
