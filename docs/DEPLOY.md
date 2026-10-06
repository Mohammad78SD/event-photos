# Deploying to a VPS

This runs on a **shared VPS** that already hosts other sites, each its own isolated
Docker Compose project. One shared edge nginx container (`edge-nginx-1`, from the
`edge` compose project at `/home/deploy/edge`) owns host ports 80/443 and routes by
`server_name` to each site's own container. This project follows that pattern:

- Our own isolated stack (`db`, `redis`, `app`, `worker`, `nginx`) — no ports
  published to the host at all.
- Our nginx container joins the shared `edge_default` network (declared as
  `edge` in `compose.prod.yaml`) so the edge nginx can reach it by container
  name (`wedding-nginx-1`), in addition to our own private network.
- TLS terminates at the edge nginx, not ours. Our `nginx.prod.conf` is plain
  HTTP internally and trusts the `X-Forwarded-Proto` the edge already set
  (see `SECURE_PROXY_SSL_HEADER` in `config/settings/prod.py`) instead of
  recomputing it.
- Certs come from the **host's existing certbot** (systemd timer) — no certbot
  container of our own.

**Disk note:** the box has limited free disk, shared with the other apps.
Set `Event.quota_gb` for the real event to fit it (the code default is 50).

## First-time setup

On your machine:

```bash
rsync -az --exclude .git --exclude media_dev --exclude pgdata_dev --exclude staticfiles \
  --exclude node_modules ./ user@your-server:/home/deploy/wedding/
```

On the server:

```bash
cd /home/deploy/wedding
cp .env.prod.example .env.prod
# edit .env.prod: DJANGO_SECRET_KEY, POSTGRES_PASSWORD

docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml exec app python manage.py createsuperuser
```

Then add `photos.example.com` to the shared edge nginx, in two steps because
the HTTPS block can't reference a certificate that doesn't exist yet:

**Step 1** — append the HTTP-only block to `/home/deploy/edge/nginx/wordpress.conf`
(alongside the existing blocks, doesn't touch them):

```nginx
server {
    listen 80;
    server_name photos.example.com;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}
```

```bash
docker exec edge-nginx-1 nginx -t && docker exec edge-nginx-1 nginx -s reload
```

**Step 2** — get the cert using the host's certbot (same webroot the other
sites on this box already use), then append the HTTPS block:

```bash
certbot certonly --webroot -w /home/deploy/certbot-webroot -d photos.example.com
```

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name photos.example.com;
    client_max_body_size 30m;
    ssl_certificate /etc/letsencrypt/live/photos.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/photos.example.com/privkey.pem;
    location / {
        proxy_pass http://wedding-nginx-1:80;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
docker exec edge-nginx-1 nginx -t && docker exec edge-nginx-1 nginx -s reload
```

Renewal is automatic — the host's `certbot.timer` renews every cert under
`/etc/letsencrypt`, ours included, no extra config needed.

## Nightly backups

Needs the `restic` binary on the host (not a pip package): `apt install restic`.

```bash
cd /home/deploy/wedding
set -a; source .env.prod; set +a
restic init   # one-time

# crontab -e:
0 3 * * * cd /home/deploy/wedding && ./scripts/backup.sh >> /var/log/wedding-backup.log 2>&1
```

Verify a backup by *restoring* one file, not by checking the cron job ran —
before the event.

## Sentry

Create a project at sentry.io, put its DSN in `.env.prod` as `SENTRY_DSN`,
restart `app` and `worker`. Wiring is already in `config/settings/prod.py`.

## Load rehearsal

```bash
python3 scripts/load_test.py https://photos.example.com <event-slug> 30
```

## Redeploying after a code change

**Build the front-end assets first.** The prod image has no node in it, so
`static/dist/` is shipped as built files by rsync. Skip this and the server
keeps serving the previous CSS/JS with no error anywhere:

```bash
npm run build      # build:css + build:js
```

```bash
rsync -az --exclude .git --exclude media_dev --exclude pgdata_dev --exclude staticfiles \
  --exclude node_modules --exclude .env --exclude .DS_Store --exclude .kilo \
  --exclude .pytest_cache --exclude '__pycache__' --exclude '*.pyc' \
  -e "ssh -i ~/.ssh/your_key" ./ user@your-server:/home/deploy/wedding/
ssh user@your-server 'cd /home/deploy/wedding &&
  docker compose -f compose.prod.yaml up -d --build &&
  until docker compose -f compose.prod.yaml exec -T app \
        python -c "import socket; socket.create_connection((\"127.0.0.1\", 8000), 2)" 2>/dev/null;
  do sleep 2; done &&
  docker compose -f compose.prod.yaml restart nginx'
```

**The wait loop is load-bearing.** The `app` container runs `migrate` and
`collectstatic` before gunicorn binds, which takes a few seconds. Restarting
nginx before that finishes is just as broken as not restarting it at all: nginx
resolves `app`, gets connection-refused, caches it, and every request 502s until
you restart nginx *again*. This bit twice during the first deploys.

`migrate` and `collectstatic` run automatically as part of the `app`
container's start command.

**Why `restart nginx` is on the end, and not optional.** `--build` recreates
the `app` container, which gives it a new IP on the private network. Our
`nginx.prod.conf` uses a literal `proxy_pass http://app:8000`, which nginx
resolves **once at config load** — so an nginx container that wasn't recreated
keeps connecting to the dead container's old address and every request returns
502 until it is restarted. This took the live site down for about a minute. Always re-check the domain after deploying, not just `compose ps` —
`ps` showed all five containers healthy while the site was serving 502s.

**Why the extra excludes.** The original command synced `.env` — the *dev*
env file, dev `DJANGO_SECRET_KEY` and `DEBUG=True` — up to the production box.
It is inert there (`env_file: .env.prod` wins, and `prod.py` hard-sets
`DEBUG = False`), but there is no reason to put a dev secret on the server.
It also pushed `.DS_Store`, `.pytest_cache`, and `.kilo/worktrees/`, which
holds a complete stale duplicate of the repo — junk on a box with ~20GB free
that has to hold the event's photos. Check first with `--dry-run
--itemize-changes`; the output should be only the files you actually changed.

**Smoke test after every deploy**, substituting the real event slug:

```bash
S=<event-slug>; B=https://photos.example.com
for p in "/e/$S/" "/e/$S/hello/" "/e/$S/gallery/" "/e/$S/live/"; do
  printf "%-40s %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' $B$p)"
done
```

All four must be 200. `https://photos.example.com/` itself returns 404 by
design — there is no root route, the app starts at `/e/<slug>/`.
