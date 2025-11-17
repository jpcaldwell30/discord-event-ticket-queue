# Deploying the Discord Event Ticket Queue Bot on Oracle Cloud Free Tier

This guide walks through a minimal, free-tier-friendly setup to run the bot on Oracle Cloud. The steps assume you already have a Discord bot token and an EDMTrain API key.

## 1. Prepare your Oracle Cloud tenancy
1. Sign in to the Oracle Cloud Console and ensure your region is set to one that supports the Always Free Compute shape (e.g., `VM.Standard.A1.Flex`).
2. In the **Identity & Security → Compartments** page, create a dedicated compartment for the bot (easier to scope policies and clean up later).
3. Under **Identity & Security → Policies**, create a policy in the root compartment that allows your user group to manage resources in the bot compartment, for example:
   ```
   allow group <YourGroupName> to manage all-resources in compartment <BotCompartmentName>
   ```

## 2. Create networking (VCN)
1. Go to **Networking → Virtual Cloud Networks** and create a new VCN in the bot compartment.
2. Accept the wizard defaults for **Public Subnet** (needed so Discord can reach your instance when you run slash command interactions), but ensure the subnet has a public CIDR like `10.0.0.0/24`.
3. In the subnet’s **Security List**, add an **Ingress Rule** for:
   - **Source CIDR**: `0.0.0.0/0`
   - **IP Protocol**: TCP
   - **Destination Port Range**: `443` (if you plan to receive interactions over HTTPS) or the port you expose for health checks only. Outbound rules can stay open by default.
4. If you prefer fine-grained control, create a **Network Security Group** (NSG) and place the compute instance in it, then add the ingress rule above to the NSG instead of the Security List.

## 3. Provision a compute instance
1. Navigate to **Compute → Instances** and create a new instance in the bot compartment.
2. Choose the Always Free shape **`VM.Standard.A1.Flex`** (Ampere) or **`VM.Standard.E2.1.Micro`**, set OCPUs and memory within free limits (e.g., `1 OCPU`, `6 GB RAM` for A1).
3. Select an OS image with long-term support (Ubuntu 22.04 is a common choice).
4. Upload your SSH public key when prompted so you can SSH into the instance.
5. Place the instance in the public subnet you created and attach the NSG if you configured one.
6. After creation, note the **Public IP** of the instance.

## 4. Harden access
1. On first login, create a non-root user and add it to the `sudo` group.
2. Disable password SSH authentication by editing `/etc/ssh/sshd_config` (set `PasswordAuthentication no`) and restart SSH: `sudo systemctl restart sshd`.
3. Configure a basic firewall with `ufw` (Ubuntu) to allow only SSH and the bot’s inbound port, for example:
   ```bash
   sudo ufw allow ssh
   sudo ufw allow 443/tcp   # only if you terminate HTTPS on the instance
   sudo ufw enable
   ```

## 5. Install runtime dependencies
1. Update packages: `sudo apt update && sudo apt upgrade -y`.
2. Install Python and Git: `sudo apt install -y python3 python3-venv python3-pip git`.
3. (Optional) Install a reverse proxy such as Nginx if you intend to serve HTTPS directly from the instance.

## 6. Deploy the bot code
1. Clone the repository onto the instance:
   ```bash
   git clone https://github.com/<your-org>/discord-event-ticket-queue.git
   cd discord-event-ticket-queue
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Initialize the SQLite database (runs automatically on first start). The repo already enables foreign key enforcement.

## 7. Configure environment variables
Set the following environment variables (e.g., in a `.env` file sourced by your service unit):

- `DISCORD_TOKEN`: your Discord bot token
- `DISCORD_CLIENT_ID`: bot application client ID (needed for slash command sync)
- `EDMTRAIN_API_KEY`: EDMTrain API key (optional; only required for importing events)
- `BOT_GUILD_IDS`: optional comma-separated guild IDs to limit command sync during testing

Example `.env`:
```bash
DISCORD_TOKEN=your_bot_token
DISCORD_CLIENT_ID=123456789012345678
EDMTRAIN_API_KEY=your_edmtrain_key
BOT_GUILD_IDS=987654321098765432,123123123123123123
```

## 8. Run the bot as a service
1. Create a systemd unit file `/etc/systemd/system/discord-ticket-bot.service`:
   ```ini
   [Unit]
   Description=Discord Event Ticket Queue Bot
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/home/<botuser>/discord-event-ticket-queue
   Environment=PYTHONUNBUFFERED=1
   EnvironmentFile=/home/<botuser>/discord-event-ticket-queue/.env
   ExecStart=/home/<botuser>/discord-event-ticket-queue/.venv/bin/python bot.py
   Restart=on-failure
   User=<botuser>
   Group=<botuser>

   [Install]
   WantedBy=multi-user.target
   ```
2. Reload systemd and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable discord-ticket-bot
   sudo systemctl start discord-ticket-bot
   sudo systemctl status discord-ticket-bot
   ```

## 9. Optional: HTTPS ingress for interactions
If you plan to receive interactions (e.g., via a separate webhook), terminate TLS with Nginx or a load balancer:
1. Install Nginx: `sudo apt install -y nginx`.
2. Obtain TLS certificates (Let’s Encrypt via `certbot` if you own a domain).
3. Create an Nginx server block that proxies to your bot’s HTTP listener (if implemented) and exposes port 443.
4. Add matching inbound rules (port 443) in the Security List/NSG and firewall.

## 10. Backups and maintenance
- Use `git pull` to deploy updates and restart the service.
- Periodically back up the SQLite database file (`database/data.sqlite`) to Object Storage or block storage.
- Monitor logs with `journalctl -u discord-ticket-bot` and ensure the free-tier OCPU/memory metrics stay within limits.

## 11. Cost control tips
- Keep the instance in a single Availability Domain and avoid paid shapes.
- Remove unused block volumes and public IPs after tests.
- Use NSGs instead of wide-open Security Lists for tighter ingress control.

With these steps, you can keep the bot within Oracle Cloud’s Always Free limits while exposing it securely to Discord.
