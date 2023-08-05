from tinkoff.invest.retrying.aio.client import AsyncRetryingClient
from tinkoff.invest.retrying.settings import RetryClientSettings
import os
from dotenv import load_dotenv
import logging
import asyncio
from pickle import dumps
import redis.asyncio as redis
from celery import Celery
from celery.schedules import crontab


logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG
)

load_dotenv()
RETRY_SETTINGS = RetryClientSettings(use_retry=True, max_retry_attempt=5)
RO_TOKEN = os.getenv('TCS_RO_TOKEN')
INSTRUMENTS = ('etfs', 'currencies', 'shares', 'bonds', 'futures')
celery = Celery(
    'database update', broker='redis://:redis@192.168.2.100:6379/0'
)
celery.conf.beat_schedule = {
    'daily-db-update': {
        'task': 'update.update_db',
        'schedule': crontab(minute=10)
    }
}


def asset_filter(asset) -> bool:
    results = (asset.api_trade_available_flag, not asset.blocked_tca_flag)
    return all(results)


async def update():
    assets = []
    async with AsyncRetryingClient(RO_TOKEN, RETRY_SETTINGS) as client:
        for inst in INSTRUMENTS:
            insts = await getattr(client.instruments, inst)()
            assets.extend(insts.instruments)
    filtered = list(filter(asset_filter, assets))
    new_data = {a.ticker: dumps(a) for a in filtered}
    r = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)
    await r.mset(new_data)
    all_keys = set(await r.keys())
    deprecated_keys = all_keys - new_data.keys()
    if deprecated_keys:
        logging.warning(f'Deleting deprecated entries: {deprecated_keys}')
        await r.delete(*(key for key in deprecated_keys))


@celery.task
def update_db():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(update())
