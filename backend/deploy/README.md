# Deployment

Native Ubuntu VM deployment (no Docker). Qdrant runs embedded inside the backend.

**Full runbook: [`azure/README.md`](azure/README.md)**

```bash
# one-time on the VM
cp backend/.env.azure backend/.env && nano backend/.env
nano frontend/.env.production
bash backend/deploy/azure/backend-setup.sh
bash backend/deploy/azure/frontend-setup.sh

# updates
bash backend/deploy/azure/deploy-backend.sh
bash backend/deploy/azure/deploy-frontend.sh
```
