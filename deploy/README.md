# Deployment

This project deploys to a single Ubuntu VM **without Docker** — everything is
installed natively (Python venv, Node, Ollama, Redis, nginx) and managed by
systemd. Qdrant runs embedded inside the backend, so there is no vector-DB
server to install.

**Full runbook: [`deploy/azure/README.md`](azure/README.md)** — VM specs,
one-time setup scripts, independent backend/frontend update deploys, TLS,
and the SQL Server switch.

Quick view:

```bash
# one-time on the VM
cp .env.azure .env && nano .env
bash deploy/azure/backend-setup.sh
bash deploy/azure/frontend-setup.sh

# updates
bash deploy/azure/deploy-backend.sh    # or deploy-frontend.sh
```
