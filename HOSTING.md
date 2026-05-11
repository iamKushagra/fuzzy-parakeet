# Hosting — Confluent AEO Dashboard

The dashboard runs on this EC2 box and is exposed publicly via a Cloudflare Quick Tunnel. Three systemd units do the work; all start on boot.

| Unit | Purpose |
|---|---|
| `confluent-aeo-web.service` | Flask dashboard served by Gunicorn on `127.0.0.1:5050` |
| `confluent-aeo-tunnel.service` | `cloudflared` quick tunnel → `127.0.0.1:5050` |
| `confluent-aeo-agent.timer` | Fires `confluent-aeo-agent.service` daily at **13:30 UTC (7:00 PM IST)** |
| `confluent-aeo-agent.service` | One-shot run of `aeo_agent.py` (scrape → draft → digest) |

All units read env vars from `/home/ec2-user/aeo/.env`.

## Get the current public URL

```bash
sudo journalctl -u confluent-aeo-tunnel.service --since '10 minutes ago' \
  | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```

> The trycloudflare.com URL is stable while the tunnel service stays up. It **changes** every time `cloudflared` restarts (crash, `systemctl restart confluent-aeo-tunnel`, reboot). For a permanent URL, see "Upgrade to a named tunnel" below.

## Common operations

```bash
sudo systemctl status confluent-aeo-web confluent-aeo-tunnel confluent-aeo-agent.timer

sudo journalctl -u confluent-aeo-web -f
sudo journalctl -u confluent-aeo-tunnel -f
sudo journalctl -u confluent-aeo-agent -n 200

sudo systemctl start confluent-aeo-agent.service

sudo systemctl restart confluent-aeo-web
sudo systemctl restart confluent-aeo-tunnel

systemctl list-timers confluent-aeo-agent.timer
```

## Upgrade to a named tunnel (permanent URL on your own domain)

The quick tunnel is convenient but the URL changes on every `cloudflared` restart. For a stable URL like `https://aeo.<yourdomain>.com`, create a named tunnel (free, requires a Cloudflare account and a domain on Cloudflare DNS):

```bash
cloudflared tunnel login

cloudflared tunnel create confluent-aeo

sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml >/dev/null <<'YAML'
tunnel: confluent-aeo
credentials-file: /home/ec2-user/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: aeo.yourdomain.com
    service: http://127.0.0.1:5050
  - service: http_status:404
YAML

cloudflared tunnel route dns confluent-aeo aeo.yourdomain.com

sudo sed -i 's|ExecStart=.*|ExecStart=/usr/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run confluent-aeo|' \
    /etc/systemd/system/confluent-aeo-tunnel.service
sudo systemctl daemon-reload
sudo systemctl restart confluent-aeo-tunnel
```

Your team now uses `https://aeo.yourdomain.com` forever.

## Adding access control later

Pair a named tunnel with **Cloudflare Access** to restrict to `@confluent.io` emails (free for up to 50 users) — set up in the Cloudflare Zero Trust dashboard once the named tunnel is live. No code changes needed.

## File map

```
/etc/systemd/system/confluent-aeo-web.service     # Flask + Gunicorn
/etc/systemd/system/confluent-aeo-tunnel.service  # cloudflared
/etc/systemd/system/confluent-aeo-agent.service   # one-shot agent run
/etc/systemd/system/confluent-aeo-agent.timer     # daily 13:30 UTC trigger

/home/ec2-user/aeo/                               # project + .venv + SQLite DB
/home/ec2-user/aeo/aeo_agent.db                   # state (dedup, drafts, scores)
/home/ec2-user/aeo/aeo_agent.log                  # agent run log
```
