Microservice - API with basic assets info, using TCS assets api.
Updates database on a daily basis and gives an endpoint /ticker/ to find asset info by its ticker.
Requires a .env file with TCS_RO_TOKEN and REDIS_URL supplied, since it's using Redis database to store info. The Dockerfile builds an image for a Raspberry Pi 4 64-bit system.

```
docker run --name tcs_base -d --restart unless-stopped --network=host tcs_base
```