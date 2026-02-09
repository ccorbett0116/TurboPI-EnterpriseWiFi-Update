# Hiwonder Robot Wi-Fi Setup (WPA2-Enterprise / eduroam)

This patch modifies the Hiwonder toolbox `wifi.py` to support WPA2-Enterprise (802.1X) networks like **eduroam**, while preserving the existing AP and WPA2-PSK functionality.

## What This Fixes

The stock `wifi.py` has several issues:

1. **No WPA2-Enterprise support** — STA mode only handles WPA2-PSK (simple password networks).
2. **Destroys all NetworkManager connections** — `disconnect()` runs `rm /etc/NetworkManager/system-connections/*`, wiping every saved connection on the system.
3. **Forces AP mode on failure** — The main loop hardcodes `WIFI_MODE = 1` after any failure, ignoring your config.
4. **Broken config reload** — `importlib.reload()` ignores `sys.path` changes, so only the first config file found is ever read.

## Prerequisites

- SSH/VNC access to the robot
- The robot's default AP credentials (SSID: `HW-XXXXXXXX`, password: `hiwonder`)
- Your eduroam credentials (identity + password)
- (Optional) Your institution's CA certificate `.pem` file

## Recommended: Set Up Remote Access First

Before switching to eduroam, install a mesh VPN like [Tailscale](https://tailscale.com/) or [ZeroTier](https://www.zerotier.com/). Once the robot is on a campus network, its IP changes via DHCP and campus firewalls may block direct SSH/VNC between devices. A mesh VPN gives the robot a stable private IP you can always reach.

**The robot needs internet access to install Tailscale/ZeroTier**, and the stock `wifi.py` only supports WPA2-PSK. So you need to do this _before_ deploying the patched files, using one of:

- **WPA2-PSK Wi-Fi (Mode 2):** Temporarily connect the robot to a simple password-based network (e.g., a phone hotspot or home router) by editing `wifi_conf.py` to Mode 2 with PSK credentials.

Find the IP of the robot, by utilizing another device connected to the same network, and long pressing on the robot in the app.

Once the robot has internet, SSH in and install:

```bash
ssh pi@<robot-ip>
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

After setup, you can always reach the robot at its Tailscale IP (e.g., `100.x.y.z`) or MagicDNS hostname, even after switching to eduroam.

## Setup Steps

### 1. Connect to the Robot

Connect your computer to the robot's AP (`HW-XXXXXXXX`, password `hiwonder`), then SSH in:

```bash
ssh pi@192.168.149.1
```

### 2. Back Up the Original Files

```bash
cp /home/pi/hiwonder-toolbox/wifi.py /home/pi/hiwonder-toolbox/wifi.py.bak
cp /home/pi/hiwonder-toolbox/wifi_conf.py /home/pi/hiwonder-toolbox/wifi_conf.py.bak
```

### 3. Deploy the Patched Files

From a machine with this repo cloned:

```bash
scp wifi.py wifi_conf.py pi@192.168.149.1:/home/pi/hiwonder-toolbox/
```

Or directly on the robot, clone and copy:

```bash
cd /tmp
git clone https://github.com/ccorbett0116/TurboPI-EnterpriseWiFi-Update.git
cp TurboPI-EnterpriseWiFi-Update/wifi.py /home/pi/hiwonder-toolbox/wifi.py
cp TurboPI-EnterpriseWiFi-Update/wifi_conf.py /home/pi/hiwonder-toolbox/wifi_conf.py
```

### 4. Edit the Config

Edit `/home/pi/hiwonder-toolbox/wifi_conf.py` with your credentials:

```bash
nano /home/pi/hiwonder-toolbox/wifi_conf.py
```

For **eduroam (WPA2-Enterprise)**:

```python
WIFI_MODE = 2
WIFI_STA_SSID = 'eduroam'
WIFI_STA_SECURITY = "eap"

WIFI_EAP_METHOD = "peap"
WIFI_EAP_IDENTITY = "youruser@youruniversity.ca"
WIFI_EAP_ANON_IDENTITY = "youruser@youruniversity.ca"
WIFI_EAP_PASSWORD = "yourpassword"
WIFI_EAP_CA_CERT = "/usr/share/ca-certificates/eduroam.pem"
WIFI_EAP_PHASE2 = "mschapv2"
```

For **WPA2-PSK (regular home/lab Wi-Fi)**:

```python
WIFI_MODE = 2
WIFI_STA_SSID = 'YourNetworkName'
WIFI_STA_SECURITY = "psk"
WIFI_STA_PASSWORD = "yourwifipassword"
```

To **stay in AP mode** (default Hiwonder behavior):

```python
WIFI_MODE = 1
```

### 5. (Optional) Install CA Certificate

The CA certificate lets the robot verify it's connecting to a legitimate eduroam access point. This is optional but recommended.

1. Go to [cat.eduroam.org](https://cat.eduroam.org/) and select your institution.
2. Click **"Choose another installer to download"**, select **Linux**, then download the installer.
3. The downloaded file is a Python script. Open it in a text editor and search for `BEGIN CERTIFICATE` (typically around lines 1327-1395).
4. You'll find a string containing two PEM certificates. Copy the entire contents of that string (both `-----BEGIN CERTIFICATE-----` ... `-----END CERTIFICATE-----` blocks) and save it to a new file called `eduroam.pem`.
5. Copy it to the robot:

```bash
sudo cp eduroam.pem /usr/share/ca-certificates/eduroam.pem
```

### 6. Clear Stale Cache and Old Connections

```bash
# Remove cached bytecode (may have old WIFI_MODE=1 baked in)
rm -f /home/pi/hiwonder-toolbox/__pycache__/wifi_conf.cpython-*.pyc

# Remove the existing AP connection so it doesn't auto-reconnect
nmcli connection down HW-* 2>/dev/null
nmcli connection delete HW-* 2>/dev/null
```

### 7. Enable and Start the Service

```bash
sudo systemctl enable wifi.service
sudo systemctl start wifi.service
```

### 8. Verify

```bash
# Check service status
systemctl status wifi.service

# Check active connection
nmcli connection show --active

# Check the log
cat /home/pi/hiwonder-toolbox/wifi.log

# Full service log
journalctl -u wifi.service -b --no-pager
```

You should see log lines like:

```
WiFi tool - ... - INFO - Config loaded from: /home/pi/hiwonder-toolbox/wifi_conf.py
WiFi tool - ... - INFO - STA mode: security=eap, SSID=eduroam
WiFi tool - ... - INFO - Connected to eduroam
```

## Config Reference

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `WIFI_MODE` | `1` or `2` | `1` | 1 = AP mode, 2 = STA (client) mode |
| `WIFI_AP_SSID` | string | `HW-<serial>` | AP mode SSID (must start with `HW-`) |
| `WIFI_AP_PASSWORD` | string | `hiwonder` | AP mode password (min 8 chars) |
| `WIFI_STA_SSID` | string | — | Network name to connect to |
| `WIFI_STA_SECURITY` | `psk` or `eap` | `psk` | Security type for STA mode |
| `WIFI_STA_PASSWORD` | string | — | Password for WPA2-PSK |
| `WIFI_EAP_METHOD` | `peap`, `ttls`, `tls` | `peap` | EAP method |
| `WIFI_EAP_IDENTITY` | string | — | 802.1X username (e.g., `user@university.ca`) |
| `WIFI_EAP_ANON_IDENTITY` | string | — | Anonymous/outer identity (optional) |
| `WIFI_EAP_PASSWORD` | string | — | 802.1X password |
| `WIFI_EAP_CA_CERT` | file path | — | Path to CA certificate PEM (optional) |
| `WIFI_EAP_PHASE2` | `mschapv2`, `gtc`, `pap` | `mschapv2` | Phase 2 (inner) auth method |
| `WIFI_FALLBACK_TO_AP` | `True` or `False` | `False` | Fall back to AP mode if STA fails |

## Troubleshooting

**Robot still creates AP after update:**
- Delete bytecode cache: `rm -f /home/pi/hiwonder-toolbox/__pycache__/wifi_conf.cpython-*.pyc`
- Check that `wifi.service` is enabled: `systemctl status wifi.service`
- Check if `/etc/wifi/wifi_conf.py` exists with `WIFI_MODE = 1` and remove/update it

**EAP connection fails:**
- Verify credentials: `nmcli connection show HW-STA` (check 802-1x settings)
- Check if CA cert exists: `ls -la /usr/share/ca-certificates/eduroam.pem`
- Try without CA cert first (remove `WIFI_EAP_CA_CERT` line from config)
- Check NetworkManager logs: `journalctl -u NetworkManager -b --no-pager`

**Need to get back to AP mode:**
- Edit config: set `WIFI_MODE = 1` in `/home/pi/hiwonder-toolbox/wifi_conf.py`
- Restart: `sudo systemctl restart wifi.service`

**Lost SSH access after switching to STA:**
- The robot's IP will change. Check your router/DHCP server for the new IP, or use:
  ```bash
  # From another machine on the same network
  ping -c1 <robot-hostname>
  # Or scan the subnet
  nmap -sn 192.168.1.0/24
  ```

## Safety Notes

- This patch **never** runs `rm /etc/NetworkManager/system-connections/*`
- Only connections named `HW-*` or `HW-STA` (created by this script) are ever deleted
- Manually configured connections (eduroam, VPN, etc.) are preserved
- The script no longer force-overrides `WIFI_MODE` to AP after failures
