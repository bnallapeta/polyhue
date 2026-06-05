# Orange Pi 5 Plus — Setup Notes

Everything needed to find, connect to, and work with the Pi for the polyhue demo.

---

## Hardware

- **Board:** Orange Pi 5 Plus (Rockchip RK3588, aarch64, 16GB RAM)
- **OS storage:** SD card (58GB, 70% used — OS lives here)
- **Data storage:** 500GB SSD mounted at `/storage` (469GB, 2% used)
- **No HDMI — headless only.**

## OS

- Orange Pi OS 1.2.0 (Ubuntu Jammy / 22.04 base)
- Kernel: `6.1.43-rockchip-rk3588`

## Network

The Pi is configured to join a **mobile hotspot** (Bharath's phone). As long as your laptop and the Pi are both on the hotspot, it's reachable.

- **mDNS hostname:** `orangepi5plus.local`
- IP is DHCP so it changes. Always use the hostname, not the IP.

## SSH Access

### Quick connect

```bash
ssh pi
```

(Requires the SSH config entry below — no password prompt.)

### Credentials (fallback)

```bash
ssh orangepi@orangepi5plus.local
# password: orangepi
```

### SSH config entry (`~/.ssh/config` on the Mac)

```
Host pi
    HostName orangepi5plus.local
    User orangepi
    IdentityFile ~/.ssh/orangepi
```

### Key

- Private key: `~/.ssh/orangepi` (ed25519)
- Public key copied to Pi's `~/.ssh/authorized_keys` on 2026-06-05

### Sudo

Passwordless sudo configured on 2026-06-05:
```bash
echo 'orangepi ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/orangepi
```

## How we found it (for future debugging)

1. `arp -a` showed one unknown device on the hotspot network.
2. Port 22 was closed — `~/.ssh/known_hosts` on the Mac had `orangepi5plus.local` from a prior neural-babel session, which revealed the hostname.
3. `orangepi5plus.local` resolves via mDNS when on the same network segment.
4. Used `sshpass` for non-interactive password SSH (the Bash tool has no TTY):
   ```bash
   sshpass -p 'orangepi' ssh orangepi@orangepi5plus.local "..."
   ```

## System at first login (2026-06-05)

```
CPU temp:    39°C
Memory:      4% of 15.59G used
Storage SD:  70% of 58G used
Storage SSD: 2% of 469G used
Uptime:      15 min
```

## Toolchain installed (2026-06-05)

- `spin 3.6.3` — `/usr/local/bin/spin` (matches Mac version)
- `wkg 0.15.1` — `/usr/local/bin/wkg`

Both installed as single binaries, no package manager.

## Polyhue deployment

Repo cloned at `~/work/polyhue`:
```bash
git clone https://github.com/bnallapeta/polyhue.git ~/work/polyhue
```

Artifact pulled from ghcr.io into `dist/`:
```bash
wkg oci pull ghcr.io/bnallapeta/polyhue:latest -o ~/work/polyhue/dist/polyhue.wasm
```

## Starting the stack manually

Two processes, started manually after each boot (not systemd — intentional for the demo):

```bash
# Terminal 1 — MCP server on :3000
cd ~/work/polyhue
spin up --listen 0.0.0.0:3000 -f dist/polyhue.wasm

# Terminal 2 — audience proxy on :8080
cd ~/work/polyhue/audience
python3 serve.py
```

Or via nohup if running headless:
```bash
cd ~/work/polyhue
nohup spin up --listen 0.0.0.0:3000 -f dist/polyhue.wasm > /tmp/spin.log 2>&1 &
nohup python3 audience/serve.py > /tmp/audience.log 2>&1 &
```

## Verifying the stack is up

```bash
curl -s -X POST http://localhost:8080/color \
  -H "Content-Type: application/json" \
  -d '{"seed":"alice"}'
# → {"hsl": "hsl(213, 86%, 56%)", "language": "python", "routed_to": "py"}
```

Audience page: `http://orangepi5plus.local:8080`

## Pre-show checks (run from the Mac)

```bash
# Smoke test — all 5 checks must pass
BASE=http://orangepi5plus.local:8080 python3 scripts/smoke-test.py

# Stress test — 200 simulated clients, verify 200/200 delivery
BASE=http://orangepi5plus.local:8080 python3 scripts/stress-sse.py -n 200
```

Results on 2026-06-05:
- Smoke test: 5/5 pass
- Stress test: 200/200, 170ms trigger RTT over WiFi, 0 errors

## Remaining before talk

- [ ] Rehearse full 9-minute demo block end-to-end
