# Deploying the Dr.Retina backend to any Linux VM

Runs the API, the worker and the AI service on one Ubuntu VM with Docker Compose.
Caddy provides automatic HTTPS. The frontend stays on Vercel. The database stays on Supabase.

Works the same on Google Cloud, DigitalOcean, Azure, AWS, Hetzner and similar.

## Recommended VM

2 vCPU, 8 GB RAM, 30 GB disk, Ubuntu 24.04 (4 GB works but leaves little headroom for the AI service).
Reserve a **static public IP** and allow inbound TCP 22, 80 and 443.

## Steps

### 1. Create the VM and connect
Create it in the provider console, attach a static IP, open ports 80 and 443, then SSH in.

### 2. Get the code
```bash
git clone https://github.com/Keerthivasan-7/Dr-Retina.git
cd Dr-Retina
bash deploy/setup-vm.sh      # installs Docker, swap, firewall
exit                          # log out and back in once
```

### 3. Copy the model checkpoints (from your laptop, ~230 MB)
The checkpoints are not in git. From PowerShell on your laptop, in the project folder:
```powershell
scp -r reports\checkpoints USER@VM_IP:~/Dr-Retina/deploy/models/
```
Only these five files are needed (the command above copies extra folders, which is fine):
- `p0_baseline_resnet50/best.pt` and `calibration.json`
- `p0_fiqa_effnet_b0/best.pt`
- `p2_lesion_segmentation/best.pt`
- `p2d_lesion_segmentation_v2/best.pt`

Check on the VM: `ls deploy/models/checkpoints/` should show those folders.

### 4. Configure
```bash
cd ~/Dr-Retina/deploy
cp .env.example .env
nano .env
```
- `DOMAIN`: `<ip-with-dashes>.sslip.io` (for example `34-93-10-20.sslip.io`) needs no domain purchase.
  Or a real name such as `api.drretina.app` with a DNS A record pointing to the VM IP.
- Fill the Supabase values from `website/Dr.Retina---AI-based-healthcare-webapp-main/backend/.env`.
- Use the **pooler** database URLs (IPv4). The direct `db.<ref>.supabase.co` host is IPv6-only and fails on most VMs.
- `API_DATABASE_URL` uses the `retina_api` role and `WORKER_DATABASE_URL` uses `retina_worker`.
- `AI_SERVICE_KEY`: generate with `openssl rand -hex 32`.

### 5. Start
```bash
bash deploy/deploy.sh
```
The first build downloads PyTorch and takes about 10 minutes. The AI service needs up to ~2 minutes to load its models.
When it finishes, `https://<DOMAIN>/health/ready` should return `{"status":"ready"}`.

### 6. Point Vercel at it (one time)
In the Vercel project (`dr-retina-web`) set:
- `API_INTERNAL_BASE_URL` = `https://<DOMAIN>/api/v1`
- `APP_URL` = `https://dr-retina-web.vercel.app`

Then redeploy. The tunnel and your laptop are no longer involved.

## Updating
```bash
cd ~/Dr-Retina && git pull && bash deploy/deploy.sh
```

## Useful commands
```bash
cd ~/Dr-Retina/deploy
docker compose ps                  # health of every service
docker compose logs -f worker      # follow one service
docker compose logs --tail 100 ai
docker compose restart ai
```
All services use `restart: always`, so they come back after crashes and VM reboots.

## Moving to another provider
Repeat steps 1-6 on the new VM, then change `API_INTERNAL_BASE_URL` on Vercel to the new `DOMAIN`.
Keep a copy of `deploy/.env` and the `models/` folder somewhere safe so this takes minutes.

## Notes
- The backend refuses a non-HTTPS AI URL in production. The worker therefore reaches the AI service
  through Caddy at `https://ai.<DOMAIN>` (Caddy has a Docker network alias, so traffic stays on the VM).
  The AI service still requires its bearer key on every request.
- The AI service runs on CPU. Expect a few seconds per screening on 2 vCPUs.
- Credit hygiene: set a budget alert in the provider console.
