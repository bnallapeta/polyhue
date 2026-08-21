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

### Saved Wi-Fi profiles (NetworkManager)

NetworkManager stores each network as a profile in
`/etc/NetworkManager/system-connections/*.nmconnection`, so they survive reboots.
Higher `autoconnect-priority` wins when several networks are in range.

| Profile | SSID | Priority | Notes |
|---|---|---|---|
| `Not Connected` | `Not Connected` | 10 | Home router (yes, that's the SSID) |
| `iPhone-Hotspot` | `Bharath Nallapeta’s iPhone` | 5 | Current phone hotspot (added 2026-08-21) |
| `Connected` | `Connected` | 0 | Old |
| `S24PlusWifi` | `S24PlusWifi` | 0 | Previous phone, stale |

```bash
nmcli -t -f NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show   # list
```

### Adding a new hotspot (e.g. after changing phones)

**Gotcha:** iOS names devices with a *curly* apostrophe (`’`, U+2019), not `'`.
NetworkManager matches the SSID byte-for-byte, so copy the SSID from a live scan
rather than typing it:

```bash
sudo nmcli device wifi rescan; sleep 5; nmcli -f SSID,SIGNAL device wifi list

sudo nmcli connection add type wifi con-name "iPhone-Hotspot" ifname wlP2p33s0 \
  ssid "Bharath Nallapeta’s iPhone" -- \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<password>" \
  connection.autoconnect yes connection.autoconnect-priority 5
```

Verify the stored bytes contain `226;128;153` (UTF-8 for `’`):

```bash
sudo grep -a '^ssid=' /etc/NetworkManager/system-connections/iPhone-Hotspot.nmconnection
```

**Testing without locking yourself out.** Switching the Pi to the hotspot kills
your SSH session if your laptop is on a different network. Run a detached script
that switches over, checks connectivity, then reverts — it survives the SSH drop:

```bash
ssh pi 'setsid nohup bash -c "
  sudo nmcli --wait 30 connection up iPhone-Hotspot
  sleep 4; ip -4 addr show wlP2p33s0 | grep inet; ping -c3 1.1.1.1
  sudo nmcli --wait 30 connection up \"Not Connected\"
" >/tmp/hs.log 2>&1 </dev/null &'
# wait ~60s, reconnect, then: ssh pi 'cat /tmp/hs.log'
```

A successful hotspot join shows an address in `172.20.10.0/28` — the fixed subnet
iOS Personal Hotspot hands out.

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
Public (Funnel) URL — the one on the slides: <https://orangepi5plus.tail13f9a8.ts.net>

## Bringing the demo up on stage

SSH in from a second terminal and run these two. **Do not use `make run` on the Pi** —
only `dist/polyhue.wasm` was copied there, so make sees the per-component `.wasm`
prerequisites missing and tries to rebuild with cargo/npm/componentize-py, none of
which are installed. It will fail.

```bash
ssh pi
cd ~/work/polyhue

# 1. the MCP server (takes ~10s to prepare the 42MB module on aarch64)
spin up -f dist/polyhue.wasm

# 2. in another shell: the audience proxy, with a pinned admin token
cd ~/work/polyhue/audience
ADMIN_TOKEN=<token> python3 serve.py
```

Order matters: `serve.py` proxies to `127.0.0.1:3000`, so Spin goes first.

Fire the red-flash closer from the Mac (or the Pi):

```bash
curl -X POST https://orangepi5plus.tail13f9a8.ts.net/trigger-denial \
  -H "X-Admin-Token: <token>"
```

### Funnel gotcha — check this before the talk

Funnel silently stopped forwarding on 2026-08-21: DNS resolved and TCP connected,
but the TLS handshake was reset and `tailscaled` logged *nothing* — the ingress had
lost its route to the node. `tailscale funnel status` still reported "on", so status
output is not proof it works. Config, cert, and the `funnel` node capability were all
intact; the fix was a full daemon restart:

```bash
sudo systemctl restart tailscaled
```

The only reliable check is fetching the public URL from off-network (phone on
cellular, or `curl` from anywhere that isn't your LAN):

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://orangepi5plus.tail13f9a8.ts.net/
```

`502` means Funnel is fine but nothing is listening on `:8080`. `000` means Funnel
itself is broken — restart `tailscaled`.

The URL is derived from the node's hostname (`orangepi5plus`) plus the tailnet
(`tail13f9a8.ts.net`). Both are stable, so the slide stays correct — but renaming
the node or re-authing into a different tailnet would change the URL and break it.

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
