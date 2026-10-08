# inpho-sse

A tiny Server-Sent Events (SSE) notifier (FastAPI + Uvicorn, Python 3.12). An existing
Flask API calls `POST /notify` when new data is stored; every connected browser gets a
generic `update` event and re-fetches its own data. No data, database or broker is involved:
clients live in memory, each with its own bounded `asyncio.Queue`.

| Endpoint | Access | Purpose |
|---|---|---|
| `GET /stream` | public (via Nginx) | SSE stream: `event: update` / `data: changed`, comment heartbeat every `SSE_HEARTBEAT_SECONDS` |
| `POST /notify` | local only, `X-API-Key` required | Broadcast an update; returns `{"status":"sent","clients":N}` |
| `GET /health` | local only | `{"status":"ok","clients":N}` |

Slow clients: each queue holds at most 16 messages; when full the oldest is dropped, so memory stays bounded
(notifications are generic, so a client only needs the latest one).

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then set NOTIFY_API_KEY
```

## Configuration (environment or `.env`)

| Variable | Default |
|---|---|
| `NOTIFY_API_KEY` | **required** (service refuses to start without it) |
| `SSE_HOST` | `127.0.0.1` |
| `SSE_PORT` | `8021` |
| `SSE_HEARTBEAT_SECONDS` | `15` |

## Run

```bash
python run.py
```

This starts a single Uvicorn worker (required: all clients share one in-memory registry).

## systemd

```bash
sudo cp -r . /opt/inpho-sse            # with .venv and .env set up there
sudo chown -R www-data: /opt/inpho-sse && sudo chmod 600 /opt/inpho-sse/.env
sudo cp inpho-sse.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inpho-sse
journalctl -u inpho-sse -f             # view logs
```

The unit uses `Restart=always`, so it restarts automatically.

## Nginx

See `nginx-inpho-sse.conf`: it proxies only `https://metrics.inpho.ie/stream` to
`http://127.0.0.1:8021/stream` with `proxy_buffering off`. `/notify` and `/health` are not exposed.

## Flask example

```python
import os, requests

def notify_sse():
    try:
        requests.post("http://127.0.0.1:8021/notify",
                      headers={"X-API-Key": os.environ["NOTIFY_API_KEY"]}, timeout=2)
    except requests.RequestException:
        pass  # never fail the API request because of the notifier

# after successfully storing an event:
notify_sse()
```

## Browser example

```js
const es = new EventSource("/stream");
es.addEventListener("update", () => loadIncoming());
```

## Testing by hand

```bash
curl -N http://127.0.0.1:8021/stream
curl -X POST -H "X-API-Key: $NOTIFY_API_KEY" http://127.0.0.1:8021/notify
curl http://127.0.0.1:8021/health
```

## Automated tests

```bash
pip install -r requirements-dev.txt
pytest
```
