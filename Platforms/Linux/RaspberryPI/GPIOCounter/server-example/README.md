# Server-side example (optional)

The counter logs locally to an RRD database, but `gpiocounter.py` can also POST
each per-minute value to a web endpoint (see the commented-out `savevalue.php`
hint in that script). This folder is an **example** of what the receiving side
could look like — a small PHP endpoint plus a browser chart.

| File | Role |
|------|------|
| `counter-endpoint.php` | Stores posted values in MySQL and serves the history back as JSON. |
| `chart.html` | Fetches that JSON and draws it (Google Charts cumulative + Dygraph per-minute). |

## Flow

```
gpiocounter.py  --POST name,value-->  counter-endpoint.php  -->  MySQL
chart.html      --GET  name (JSON)-->  counter-endpoint.php  <--  MySQL
```

Endpoint usage:

* `counter-endpoint.php?createTable=1` — create the table once.
* `counter-endpoint.php?name=mysensor&value=102` (POST) — store a reading.
* `counter-endpoint.php?name=mysensor` (GET) — return the last ~10 days as JSON.

## ⚠️ Before you use it

These are illustrative, **not production-ready**:

* Replace the placeholder DB credentials (`localhost` / `mydb` / `dbuser` /
  `CHANGE_ME`) with your own, and keep real secrets out of version control
  (env vars / a config file that is git-ignored).
* CORS is wide open (`Access-Control-Allow-Origin: *`) and there is no
  authentication — anyone who knows the URL can write and read values. Lock this
  down (auth, HTTPS, input validation) for any real deployment.
* `chart.html` loads jQuery / Google Charts / Dygraph from public CDNs and points
  at `http://example.com/counter-endpoint.php` — change the URL and sensor name.
