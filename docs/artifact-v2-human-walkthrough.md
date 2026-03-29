# artiFACT v2 — Human Walkthrough

**For**: Jordan Allred
**Purpose**: Step-by-step from zero to running platform
**Prerequisite**: A2 VPS XS ordered (Ubuntu 24.04, no cPanel, Dallas)

---

## PHASE 0: Get Into Your VPS

### Step 1: Get your VPS IP

After A2 provisions the VPS, you'll get an email with:
- **IP address** (e.g., `198.50.xxx.xxx`)
- **Root password** (or SSH key, depending on what you chose)

### Step 2: SSH in from your local machine

**Mac/Linux terminal or Windows PowerShell:**
```bash
ssh root@YOUR_VPS_IP
```
Type `yes` when asked about fingerprint. Enter the password from the email.

You should see a Ubuntu prompt:
```
root@localhost:~#
```

You're in. This is real root — not cPanel jail.

### Step 3: Set up a non-root user (security hygiene)

```bash
adduser jordan
usermod -aG sudo jordan
```
Set a password when prompted. From now on, use `jordan` for daily work:
```bash
su - jordan
```

### Step 4: Point your subdomain to the VPS

In your domain registrar (wherever you manage `jordanaallred.com` DNS):

1. Add an **A record**:
   - **Name**: `artifact`
   - **Value**: `YOUR_VPS_IP`
   - **TTL**: 300

2. Wait 5-10 minutes for DNS propagation.

3. Test from your local machine:
   ```bash
   ping artifact.jordanaallred.com
   ```
   Should resolve to your VPS IP.

---

## PHASE 1: Install Docker

### Step 5: Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 6: Install Docker

```bash
# Install prerequisites
sudo apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Let your user run Docker without sudo
sudo usermod -aG docker jordan
```

**Log out and log back in** for the group change to take effect:
```bash
exit
ssh jordan@YOUR_VPS_IP
```

### Step 7: Verify Docker works

```bash
docker --version
docker compose version
docker run hello-world
```

All three should succeed. If `docker run hello-world` prints "Hello from Docker!", you're good.

---

## PHASE 2: Connect Claude Code

### Step 8: Install Claude Code on your local machine

On your **local machine** (Mac/Windows/Linux), not the VPS:

```bash
npm install -g @anthropic-ai/claude-code
```

If you don't have Node.js: install it from https://nodejs.org (LTS version).

Verify:
```bash
claude --version
```

### Step 9: SSH config for easy access

On your **local machine**, create/edit `~/.ssh/config`:

```
Host artifact-vps
    HostName YOUR_VPS_IP
    User jordan
    ForwardAgent yes
```

Now you can do `ssh artifact-vps` instead of typing the full IP.

### Step 10: Connect Claude Code to the VPS

```bash
claude --ssh artifact-vps
```

Claude Code will SSH into the VPS and operate directly on the remote filesystem. You're now developing on the VPS through Claude Code from your local machine.

**Test it**: Ask Claude Code to run `pwd` — it should show `/home/jordan`.

### Step 11: Alternative — VS Code Remote SSH

If you prefer VS Code:

1. Install the **Remote - SSH** extension
2. `Cmd+Shift+P` → "Remote-SSH: Connect to Host" → `artifact-vps`
3. VS Code opens a remote window on the VPS
4. Open terminal in VS Code → you're on the VPS
5. Run Claude Code from that terminal: `claude`

---

## PHASE 3: Initialize the Project

### Step 12: Install Git on VPS

```bash
sudo apt install -y git
git config --global user.name "Jordan Allred"
git config --global user.email "your@email.com"
```

### Step 13: Create the project directory

```bash
mkdir -p ~/artifact-v2
cd ~/artifact-v2
git init
```

### Step 14: Create the project skeleton

This is where Claude Code takes over. Tell it:

> "Read artifact-v2-master-reference.md and artifact-v2-architecture.md. Create the Sprint 0 project skeleton: pyproject.toml, Dockerfile, Dockerfile.worker, docker-compose.yml, nginx config, alembic.ini, and the full directory structure from section 3.3 of the architecture doc. Use the VPS domain artifact.jordanaallred.com."

Claude Code will create all the files directly on the VPS.

### Step 15: Start the stack

```bash
cd ~/artifact-v2
docker compose up --build
```

First run takes 3-5 minutes (downloads base images, installs Python packages). Subsequent runs take seconds.

You should see:
```
web-1     | INFO:     Uvicorn running on http://0.0.0.0:8000
worker-1  | celery@artifact ready.
postgres-1| database system is ready to accept connections
redis-1   | Ready to accept connections
```

### Step 16: Set up nginx + HTTPS

```bash
# Install nginx and certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Create nginx config
sudo tee /etc/nginx/sites-available/artifact << 'EOF'
server {
    listen 80;
    server_name artifact.jordanaallred.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
EOF

# Enable the site
sudo ln -s /etc/nginx/sites-available/artifact /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Get HTTPS certificate (free via Let's Encrypt)
sudo certbot --nginx -d artifact.jordanaallred.com --non-interactive --agree-tos -m your@email.com
```

### Step 17: Verify

Open a browser and go to:

```
https://artifact.jordanaallred.com/api/v1/health
```

You should see:
```json
{"status": "healthy", "checks": {"database": true, "redis": true}}
```

**Sprint 0 is complete.** You have a running platform.

---

## PHASE 4: Build Sprints 1-13

From here, each sprint follows the same cycle:

### The Sprint Cycle

```
1. Open Claude Code (connected to VPS)
   claude --ssh artifact-vps

2. Tell Claude Code which sprint to build:
   "Build Sprint 3 (Facts Core) per the master reference.
    Here's the DoS: [paste from master-reference.md]"

3. Claude Code creates the files, writes the code,
   runs the tests, and iterates until the DoS is met.

4. Verify in browser:
   - Hit the API endpoints manually (curl or browser)
   - Check the UI renders correctly
   - Run the test suite: docker compose exec web pytest

5. Commit:
   git add .
   git commit -m "Sprint 3: Facts Core — DoS met"

6. Move to the next sprint.
```

### Sprint Order (do not skip or reorder)

```
Sprint 0:  Infrastructure                ← DONE (Phase 3 above)
Sprint 1:  Kernel + Auth                 ← Start here next
Sprint 2:  Taxonomy
Sprint 3:  Facts Core
Sprint 4:  Queue + Approval
Sprint 5:  Signing
Sprint 6:  Search
Sprint 7:  Per-User AI + Chat
Sprint 8:  Import Pipeline
Sprint 9:  Export
Sprint 10: Feedback
Sprint 11: Presentation
Sprint 12: Admin Dashboard
Sprint 13: Polish + Harden
Sprint 14: COSMOS Port                   ← Only after COSMOS billing is sorted
```

### How to verify a sprint is done

Every sprint has a **Definition of Success** in the master reference (Section 6). Read it literally. Every bullet must be true. If any bullet is false, the sprint is not done.

Example for Sprint 1:
```
✓ POST /api/v1/auth/login returns a session cookie
✓ GET /api/v1/users/me returns the authenticated user
✓ Unauthenticated requests return 401
✓ CSRF token validated on all writes
✓ Permission resolver passes all unit tests
✓ Rate limiter blocks after threshold
✓ All kernel unit tests pass
```

---

## PHASE 5: Daily Operations

### Start the stack
```bash
cd ~/artifact-v2
docker compose up -d          # -d = background
```

### Stop the stack
```bash
docker compose down
```

### View logs
```bash
docker compose logs -f web    # Follow web container logs
docker compose logs -f worker # Follow worker container logs
```

### Run tests
```bash
docker compose exec web pytest                    # All tests
docker compose exec web pytest modules/facts/     # One module
docker compose exec web pytest -x                 # Stop on first failure
docker compose exec web pytest --cov              # With coverage report
```

### Run linting
```bash
docker compose exec web ruff check .
docker compose exec web ruff format --check .
docker compose exec web mypy artiFACT/
```

### Create a database migration
```bash
docker compose exec web alembic revision --autogenerate -m "description"
docker compose exec web alembic upgrade head
```

### Reset the database (nuclear option)
```bash
docker compose down -v        # -v = delete volumes (database data)
docker compose up -d
docker compose exec web alembic upgrade head
```

### Back up the database
```bash
docker compose exec postgres pg_dump -U artifact artifact_db > backup_$(date +%Y%m%d).sql
```

### Connect Claude Code
```bash
claude --ssh artifact-vps
# Or if already SSH'd into the VPS:
cd ~/artifact-v2
claude
```

---

## PHASE 6: Port to COSMOS

When COSMOS billing is sorted:

### Step 1: Push Docker images to COSMOS ECR

```bash
# Authenticate Docker to ECR (COSMOS provides these commands)
aws ecr get-login-password --region us-gov-west-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-gov-west-1.amazonaws.com

# Tag and push
docker tag artifact-web:latest ACCOUNT_ID.dkr.ecr.us-gov-west-1.amazonaws.com/artifact-web:latest
docker push ACCOUNT_ID.dkr.ecr.us-gov-west-1.amazonaws.com/artifact-web:latest

docker tag artifact-worker:latest ACCOUNT_ID.dkr.ecr.us-gov-west-1.amazonaws.com/artifact-worker:latest
docker push ACCOUNT_ID.dkr.ecr.us-gov-west-1.amazonaws.com/artifact-worker:latest
```

### Step 2: Create COSMOS infrastructure

```bash
cd terraform/environments/prod
terraform init
terraform apply
```

This creates: RDS PostgreSQL, ElastiCache Redis, ECS Fargate tasks, ALB, S3 buckets.

### Step 3: Run migrations

```bash
# Connect to COSMOS ECS task and run
alembic upgrade head
```

### Step 4: Migrate v1 data

```bash
python scripts/migrate_v1_to_v2.py --source v1_dump.sql --target $COSMOS_DATABASE_URL
```

### Step 5: Configure CAC auth

Update environment variables in the ECS task definition:
```
SAML_ENTITY_ID=https://artifact.cosmos.navy.mil
SAML_ACS_URL=https://artifact.cosmos.navy.mil/api/v1/auth/saml/callback
SAML_METADATA_URL=<COSMOS SAML metadata endpoint>
```

### Step 6: Verify

```
https://artifact.cosmos.navy.mil/api/v1/health
```

CAC prompt should appear. After authentication:
```
https://artifact.cosmos.navy.mil/
```

You're live on COSMOS. Cancel the A2 VPS when you're confident.

---

## QUICK REFERENCE

| Task | Command |
|------|---------|
| SSH to VPS | `ssh artifact-vps` |
| Claude Code on VPS | `claude --ssh artifact-vps` |
| Start stack | `docker compose up -d` |
| Stop stack | `docker compose down` |
| View logs | `docker compose logs -f web` |
| Run all tests | `docker compose exec web pytest` |
| Lint | `docker compose exec web ruff check .` |
| New migration | `docker compose exec web alembic revision --autogenerate -m "msg"` |
| Apply migrations | `docker compose exec web alembic upgrade head` |
| Backup DB | `docker compose exec postgres pg_dump -U artifact artifact_db > backup.sql` |
| Reset DB | `docker compose down -v && docker compose up -d` |
| Commit | `git add . && git commit -m "Sprint N: description"` |
