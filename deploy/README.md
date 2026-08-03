# Deploying OptionsSimulator to the shared VM

This app runs alongside `TradeDashBoard` on the same Oracle Cloud VM (`130.210.42.240`), fully
isolated (own directory, port, systemd service, Fyers app — see `docs/ARCHITECTURE.md`).

## Prerequisites

1. A GitHub repo for this project, with these repo secrets set:
   - `DEPLOY_HOST` = `130.210.42.240`
   - `DEPLOY_USER` = `ubuntu`
   - `DEPLOY_SSH_KEY` = the VM's private key (you add this — not something to paste into chat)
2. A Supabase project (separate from TradeDashBoard's) — `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
   `SUPABASE_DB_URL` (transaction-pooler connection string, port 6543).
3. `backend/migrations/001_options_positions.sql` run once, manually, in that Supabase project's
   SQL editor (same approach TradeDashBoard uses — no migration framework).

## One-time VM provisioning (before the first CI deploy can succeed)

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@130.210.42.240

# 1. Clone
mkdir -p /home/ubuntu/optionssimulator-app
git clone <your-repo-url> /home/ubuntu/optionssimulator-app
cd /home/ubuntu/optionssimulator-app

# 2. venv + deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r backend/requirements.txt

# 3. .env (backend) and frontend/.env — fill in real values, never commit these
cp .env.example .env
cp frontend/.env.example frontend/.env

# 4. Build the frontend once so it exists before the service starts
cd frontend && npm ci && npm run build && cd ..

# 5. systemd unit (installed, NOT started until .env is filled in and Caddy is updated)
sudo cp deploy/optionssimulator-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable optionssimulator-backend

# 6. Caddy route — see Caddy-snippet.conf for the exact block and where it goes
sudo nano /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 7. First start
sudo systemctl start optionssimulator-backend
curl http://127.0.0.1:8001/api/health
```

After this, every push to `main` runs `.github/workflows/deploy.yml`, which SSHes in, resets to
the new commit, and runs `deploy/deploy.sh` (frontend rebuild, dependency install, systemd
restart, health check with rollback on failure).
