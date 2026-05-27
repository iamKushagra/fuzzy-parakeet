# Hosting — Confluent AEO Dashboard

The dashboard runs on EC2 entirely behind **AWS networking**: nginx terminates **HTTPS** with a self-signed cert and proxies to **Gunicorn on `127.0.0.1:5050`** (loopback-only). No third-party tunnel.

> ⚠️ **Note on port 443 sharing**: this host also serves [`examgen.in`](https://examgen.in) on port 443 with a real Let's Encrypt cert. The two apps coexist cleanly — examgen is matched by SNI (`examgen.in`, `api.examgen.in`) and AEO is the `default_server` (catches all other traffic, including raw IP access). See **[Access control](#access-control--vpn-only)** for important security implications.

## systemd units

| Unit | Purpose |
|---|---|
| `confluent-aeo-web.service` | Flask dashboard via Gunicorn on **`127.0.0.1:5050`** (loopback) |
| `confluent-aeo-agent.timer` | Fires `confluent-aeo-agent.service` daily at **13:30 UTC (7:00 PM IST)** |
| `confluent-aeo-agent.service` | One-shot run of `aeo_agent.py` (scrape → draft → digest) |

All units read environment from `/home/ec2-user/aeo/.env`.

## How traffic flows

```
[ Confluent VPN user ]
         │  https://23.20.190.227
         ▼
[ AWS EC2 Security Group ]     inbound tcp/443 (currently open for examgen.in)
         │                     inbound tcp/80  (redirects to 443)
         ▼
[ nginx — TLS termination ]    self-signed cert, IP + EC2 DNS SANs, 10y validity
   │                           default_server catches IP traffic → AEO
   │                           server_name examgen.in / api.examgen.in → examgen
   ▼
[ Gunicorn on 127.0.0.1:5050 ] systemd: confluent-aeo-web.service
         │
         ▼
[ aeo_web:app (Flask) ]
         │
         ▼
[ aeo_agent.db (SQLite) ]
```

## URL to share

**`https://23.20.190.227`** (no port suffix — nginx serves on standard 443)

Browsers will show **"Not Secure / Your connection is not private"** on first visit because the cert is self-signed. Users click **Advanced → Proceed to 23.20.190.227 (unsafe)** once. Subsequent visits in that browser load normally with full encryption.

### Cert fingerprint (for users who want to verify manually)

```bash
sudo openssl x509 -in /etc/nginx/aeo-ssl/aeo.crt -noout -fingerprint -sha256
```

Share that SHA-256 fingerprint via Slack so users can compare it against what their browser shows on the warning page. Match = same cert; no MITM.

### Fetch the current public IP from the box

```bash
TOKEN=$(curl -s -X PUT 'http://169.254.169.254/latest/api/token' \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/public-ipv4
```

## Smoke-test commands

```bash
sudo ss -tlnp | grep -E ':(80|443|5050)'

curl -s --cacert /etc/nginx/aeo-ssl/aeo.crt \
    --resolve 23.20.190.227:443:127.0.0.1 \
    https://23.20.190.227/api/stats | python3 -m json.tool

curl -sk --resolve examgen.in:443:127.0.0.1 -o /dev/null \
    -w 'examgen: %{http_code}\n' https://examgen.in/

sudo nginx -t
sudo journalctl -u nginx -n 100 --no-pager
```

## Access control — VPN-only

> 🚨 **READ THIS BEFORE SHARING THE LINK BROADLY.**
>
> Port `tcp/443` on this EC2 instance is **publicly open to `0.0.0.0/0`** because examgen.in needs to be reachable from the open internet. That means `https://23.20.190.227` is **also technically reachable from the public internet right now**. Today the only thing protecting it is obscurity (nobody knows the raw IP). Once the IP gets indexed by Shodan/Censys/leaks/etc., it becomes findable.

### How to actually enforce VPN-only access

Edit `/etc/nginx/conf.d/aeo.conf` and uncomment the IP allowlist block inside the AEO `server { listen 443 ssl; ... }` block:

```nginx
allow 10.0.0.0/8;       # ← replace with your real corporate VPN CIDR(s)
allow 100.64.0.0/10;
allow 127.0.0.1;
deny  all;
```

Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

After that, anyone whose source IP isn't in the allowlist gets `403 Forbidden` from nginx — even though the SG still lets them connect on 443. examgen.in is unaffected (it's a separate server block).

### Alternative architectural fixes (more effort)

- **Move AEO to a separate HTTPS port** (e.g. `tcp/8443`) and open that port in the SG **only to VPN CIDRs**. URL becomes `https://23.20.190.227:8443`. Cleanest network-level gating but uglier URL.
- **Move examgen.in to a different EC2 box**, then tighten `tcp/443` on this box to VPN CIDRs only. Best long-term separation of concerns.
- **Use AWS Client VPN endpoint** with a private SG — only Client VPN-attached identities can hit the instance. Cleanest, but adds AWS cost.

## EC2 security group (current state & cleanup)

What's open today on this instance:

| Port | Source | Why it's there |
|---|---|---|
| `tcp/22` (SSH) | check & lock down to your IP if not already | EC2 default |
| `tcp/80` | `0.0.0.0/0` (probably) | nginx redirects to 443 |
| `tcp/443` | `0.0.0.0/0` | examgen.in needs public access |
| `tcp/5050` | VPN CIDRs (added during migration) | **No longer needed** — Gunicorn moved back to `127.0.0.1:5050`. Safe to remove. |
| `tcp/8000` | check | examgen API backend? |

You can safely remove the `tcp/5050` rule via:

1. AWS Console → **EC2 → Instances** → this instance → **Security** tab → click the SG
2. Find the inbound rule for `5050` → **Remove** → Save

Or AWS CLI:

```bash
SG_ID=sg-xxxxxxxx
VPN_CIDR=10.0.0.0/16

aws ec2 revoke-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 5050 \
    --cidr "$VPN_CIDR"
```

## Elastic IP (permanent public address)

Without an EIP, the public IPv4 changes any time the instance is **stopped & started** (simple reboots keep it). Allocate one so the team's bookmark never breaks:

1. AWS Console → **EC2 → Elastic IPs** → **Allocate Elastic IP address** → Allocate
2. Select the newly allocated EIP → **Actions → Associate Elastic IP address**
3. Instance: this EC2 instance → **Associate**

EIPs are **free while attached to a running instance**. AWS only charges if the EIP is unallocated or attached to a stopped instance.

## Common operations

```bash
sudo systemctl status confluent-aeo-web confluent-aeo-agent.timer nginx

sudo journalctl -u confluent-aeo-web -f
sudo journalctl -u nginx -f
sudo journalctl -u confluent-aeo-agent -n 200 --no-pager

sudo systemctl start confluent-aeo-agent.service

sudo systemctl restart confluent-aeo-web
sudo systemctl reload nginx

systemctl list-timers confluent-aeo-agent.timer
```

## Renewing the self-signed cert (every 10 years 🙃)

Cert expires **May 2036**. To rotate sooner, regenerate:

```bash
sudo openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -keyout /etc/nginx/aeo-ssl/aeo.key \
  -out    /etc/nginx/aeo-ssl/aeo.crt \
  -subj "/CN=confluent-aeo-monitor/O=Confluent AEO/C=US" \
  -addext "subjectAltName=IP:23.20.190.227,DNS:ec2-23-20-190-227.compute-1.amazonaws.com,DNS:localhost"
sudo systemctl reload nginx
```

Browsers that accepted the old cert will warn again on first visit after rotation.

## Optional further hardening

### A. Replace self-signed with a real cert

If you ever register an internal DNS name (e.g. `aeo.internal.confluent.io` → this EC2) or buy a cheap public domain:

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d aeo.your-domain.com
```

certbot auto-edits the nginx config, fetches a real cert, and renews it via a systemd timer. URL becomes `https://aeo.your-domain.com` with no browser warning.

### B. Basic auth (single shared password)

Even on top of VPN gating, adds a credential prompt:

```bash
sudo dnf install -y httpd-tools
sudo htpasswd -c /etc/nginx/.htpasswd confluent
```

Then inside the AEO `server { listen 443 ssl; ... }` block in `/etc/nginx/conf.d/aeo.conf` add:

```nginx
auth_basic           "Confluent AEO Dashboard";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Reload nginx.

## File map

```
/etc/systemd/system/confluent-aeo-web.service      # Gunicorn on 127.0.0.1:5050
/etc/systemd/system/confluent-aeo-agent.service    # one-shot agent
/etc/systemd/system/confluent-aeo-agent.timer      # daily 13:30 UTC
/etc/nginx/conf.d/aeo.conf                         # TLS reverse proxy
/etc/nginx/aeo-ssl/aeo.crt                         # self-signed cert (10y)
/etc/nginx/aeo-ssl/aeo.key                         # private key (root-only)

/home/ec2-user/aeo/                                # project + .venv + SQLite
/home/ec2-user/aeo/aeo_agent.db
/home/ec2-user/aeo/aeo_agent.log
```

## History

- **2026-05-11** — Initial deploy using a Cloudflare Quick Tunnel (`*.trycloudflare.com`) for the public URL.
- **2026-05-13 (morning)** — Migrated to direct EC2 hosting (Gunicorn on `0.0.0.0:5050`) behind a VPN-restricted SG rule. Cloudflare Tunnel and `cloudflared` removed. Reason: the public tunnel URL triggered InfoSec alerts for the internal team.
- **2026-05-13 (afternoon)** — Added nginx + self-signed TLS in front of Gunicorn. Gunicorn moved back to `127.0.0.1:5050` (loopback). New URL `https://23.20.190.227`. Port 5050 SG rule no longer needed but left in place pending cleanup. nginx IP allowlist added in commented form pending VPN CIDR confirmation.
