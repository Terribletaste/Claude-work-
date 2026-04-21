# API Health Check

Minimal HTTP health check endpoint using only the Python standard library.

## Run

```
python3 health_check.py
```

Then:

```
curl http://localhost:8080/health
```

Response:

```json
{"status": "ok", "uptime_seconds": 0.123}
```
