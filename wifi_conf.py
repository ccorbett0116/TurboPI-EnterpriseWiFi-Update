#!/usr/bin/python3
#coding:utf8

# =============================================================================
# WiFi Configuration
# =============================================================================
# WIFI_MODE: 1 = AP mode, 2 = STA (client) mode
# =============================================================================

WIFI_MODE = 2

# -----------------------------------------------------------------------------
# AP Mode Settings (WIFI_MODE = 1)
# -----------------------------------------------------------------------------
#WIFI_AP_SSID = 'HW-Robot'        # Must start with HW- for app compatibility
#WIFI_AP_PASSWORD = 'hiwonder'    # Min 8 characters

# -----------------------------------------------------------------------------
# STA Mode Settings (WIFI_MODE = 2)
# -----------------------------------------------------------------------------
WIFI_STA_SSID = 'eduroam'

# Security type: "psk" for WPA2-Personal, "eap" for WPA2-Enterprise
WIFI_STA_SECURITY = "eap"

# --- WPA2-PSK settings (when WIFI_STA_SECURITY = "psk") ---
#WIFI_STA_PASSWORD = 'your_wifi_password'

# --- WPA2-Enterprise / 802.1X settings (when WIFI_STA_SECURITY = "eap") ---
WIFI_EAP_METHOD = "peap"                    # peap, ttls, or tls
WIFI_EAP_IDENTITY = "user@university.ca"
WIFI_EAP_ANON_IDENTITY = "user@university.ca" # Optional, often same as identity
WIFI_EAP_PASSWORD = "password"
WIFI_EAP_CA_CERT = "/usr/share/ca-certificates/eduroam.pem"  # Optional but recommended
WIFI_EAP_PHASE2 = "mschapv2"                # mschapv2, gtc, or pap

# --- Optional: Fallback to AP mode if STA connection fails ---
WIFI_FALLBACK_TO_AP = False
