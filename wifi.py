#!/usr/bin/env python3
import os
import sys
import time
import gpiod
import logging
import netifaces
import importlib
import threading
import subprocess
import socketserver
from find_device import get_cpu_serial_number

led1_pin = 16  # 蓝色led
led2_pin = 26 
chip = gpiod.Chip('gpiochip0')
led1 = chip.get_line(led1_pin)
led1.request(consumer="led1", type=gpiod.LINE_REQ_DIR_OUT)
led2 = chip.get_line(led2_pin)
led2.request(consumer="led2", type=gpiod.LINE_REQ_DIR_OUT)
led1.set_value(0)
led2.set_value(0)

path = os.path.split(os.path.realpath(__file__))[0]
log_file_path = "%s/wifi.log"%path
if not os.path.exists(log_file_path):
    os.system('touch %s'%log_file_path)
config_file_name = "wifi_conf.py"
internal_config_file_dir_path = "/etc/wifi"
external_config_file_dir_path = path
internal_config_file_path = os.path.join(internal_config_file_dir_path, config_file_name)
external_config_file_path = os.path.join(external_config_file_dir_path, config_file_name)
led_on_time = 100
led_off_time = 100

# Connection names managed by this script (safe to delete)
MANAGED_AP_PREFIX = "HW-"
MANAGED_STA_CON_NAME = "HW-STA"

def update_globals(module):
    # Remove cached module so import_module picks up the current sys.path
    if module in sys.modules:
        del sys.modules[module]
    mdl = importlib.import_module(module)
    if "__all" in mdl.__dict__:
        names = mdl.__dict__["__all__"]
    else:
        names = [x for x in mdl.__dict__ if not x.startswith("_")]
    globals().update({k: getattr(mdl, k) for k in names})

def led_thread():
    global led_on_time
    global led_off_time
    
    local_led_on_time = 0
    local_led_off_time = 0

    count = 0
    cycle_time = 0
    while True:
        if local_led_on_time != led_on_time or local_led_off_time != led_off_time:
            local_led_on_time = led_on_time
            local_led_off_time = led_off_time
            cycle_time = local_led_on_time + local_led_off_time
            count = 0
        if count < local_led_on_time:
            led2.set_value(0)
            count += 1
        elif count < cycle_time:
            led2.set_value(1)
            count += 1
        else:
            count = 0

        time.sleep(0.01)

if __name__ == "__main__":
    ap_prefix = 'HW-'
    sn = get_cpu_serial_number()   #get cpu serial number
    WIFI_MODE = 1  #1 means AP mode, 2 means Client Mode, 3 means AP mode with eth0 internet share '
    WIFI_AP_SSID = ''.join([ap_prefix, sn[0:8]])
    WIFI_STA_SSID = "ssid"
    WIFI_AP_PASSWORD = "hiwonder"
    WIFI_STA_PASSWORD = "12345678"
    WIFI_AP_GATEWAY = "192.168.149.1"
    WIFI_CHANNEL = 36
    WIFI_FREQ_BAND = 'a' #5G
    WIFI_TIMEOUT = 15
    WIFI_LED = True
    ip = WIFI_AP_GATEWAY

    # New enterprise/EAP config keys with defaults
    WIFI_STA_SECURITY = "psk"           # "psk" or "eap"
    WIFI_EAP_METHOD = "peap"            # peap, ttls, tls
    WIFI_EAP_IDENTITY = ""
    WIFI_EAP_ANON_IDENTITY = ""         # optional
    WIFI_EAP_PASSWORD = ""
    WIFI_EAP_CA_CERT = ""               # path to PEM, optional but recommended
    WIFI_EAP_PHASE2 = "mschapv2"        # mschapv2, gtc, pap
    WIFI_EAP_DOMAIN_SUFFIX_MATCH = ""   # optional
    WIFI_EAP_ALTSUBJECT_MATCH = ""      # optional
    WIFI_FALLBACK_TO_AP = False         # if True, fallback to AP on STA failure

    logger = logging.getLogger("WiFi tool")
    logger.setLevel(logging.DEBUG)
    log_handler = logging.FileHandler(log_file_path)
    log_handler.setLevel(logging.INFO)
    log_formatter = logging.Formatter('%(name)s - %(asctime)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)

    ### read config file
    config_loaded_from = None
    if os.path.exists(config_file_name):
        update_globals(os.path.splitext(config_file_name)[0])
        config_loaded_from = os.path.abspath(config_file_name)
    if os.path.exists(internal_config_file_path):
        sys.path.insert(0, internal_config_file_dir_path)
        update_globals(os.path.splitext(config_file_name)[0])
        config_loaded_from = internal_config_file_path
    if os.path.exists(external_config_file_path):
        sys.path.insert(0, external_config_file_dir_path)
        update_globals(os.path.splitext(config_file_name)[0])
        config_loaded_from = external_config_file_path

    if config_loaded_from:
        logger.info("Config loaded from: %s" % config_loaded_from)
    else:
        logger.warning("No external config found, using defaults")
   
    def get_connect():
        """Get currently active wireless connection name"""
        try:
            result = subprocess.run(['nmcli', '-t', 'con', 'show', '--active'], stdout=subprocess.PIPE)
            active_conns = result.stdout.decode().split('\n')
            for conn in active_conns:
                if conn:
                    conn_details = conn.split(':')
                    if 'wireless' in conn_details[2]:
                        wifi = conn_details[0]
                        return wifi
        except:
            pass
        return None

    def disconnect_managed_only():
        """
        Safely disconnect and delete ONLY connections managed by this script.
        Never deletes unrelated NM connections (e.g., eduroam configured manually).
        """
        try:
            result = subprocess.run(['nmcli', '-t', 'con', 'show'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            all_conns = result.stdout.decode().strip().split('\n')

            for conn in all_conns:
                if not conn:
                    continue
                conn_details = conn.split(':')
                conn_name = conn_details[0]

                # Only delete connections we manage:
                # 1. AP connections starting with HW-
                # 2. Our STA connection named HW-STA
                if conn_name.startswith(MANAGED_AP_PREFIX) or conn_name == MANAGED_STA_CON_NAME:
                    logger.info("Disconnecting managed connection: %s" % conn_name)
                    subprocess.run(['nmcli', 'connection', 'down', conn_name],
                                   stderr=subprocess.DEVNULL)
                    subprocess.run(['nmcli', 'connection', 'delete', conn_name],
                                   stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error("Error in disconnect_managed_only: %s" % str(e))

    def enable_autoconnect():
        """Turn autoconnect on only after the profile is fully configured
        and verified working, so NetworkManager never races us."""
        subprocess.run(['nmcli', 'connection', 'modify', MANAGED_STA_CON_NAME,
                        'connection.autoconnect', 'yes'],
                       stderr=subprocess.DEVNULL)

    def connect_sta_psk(ssid, password):
        """Connect to WPA2-PSK network using nmcli connection add for persistence"""
        logger.info("STA mode: Connecting to '%s' with WPA2-PSK" % ssid)

        # Delete existing managed STA connection if present
        subprocess.run(['nmcli', 'connection', 'delete', MANAGED_STA_CON_NAME],
                       stderr=subprocess.DEVNULL)

        # Create the profile with autoconnect DISABLED so NetworkManager
        # cannot start activating it on its own before we bring it up
        # ourselves. Autoconnect is enabled only after a successful 'up'.
        result = subprocess.run([
            'nmcli', 'connection', 'add',
            'type', 'wifi',
            'ifname', 'wlan0',
            'con-name', MANAGED_STA_CON_NAME,
            'ssid', ssid,
            'wifi-sec.key-mgmt', 'wpa-psk',
            'wifi-sec.psk', password,
            'connection.autoconnect', 'no'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            logger.error("Failed to create PSK connection: %s" % result.stderr.decode())
            return False

        # Bring up the connection
        result = subprocess.run(['nmcli', 'connection', 'up', MANAGED_STA_CON_NAME],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            logger.error("Failed to activate PSK connection: %s" % result.stderr.decode())
            return False

        enable_autoconnect()
        return True

    def connect_sta_eap(ssid, identity, password, anon_identity="", ca_cert="",
                        eap_method="peap", phase2="mschapv2",
                        domain_suffix_match="", altsubject_match=""):
        """Connect to WPA2-Enterprise (802.1X) network"""
        logger.info("STA mode: Connecting to '%s' with WPA2-Enterprise (%s)" % (ssid, eap_method))

        # Delete existing managed STA connection if present
        subprocess.run(['nmcli', 'connection', 'delete', MANAGED_STA_CON_NAME],
                       stderr=subprocess.DEVNULL)

        # Create the profile in a SINGLE nmcli call, fully configured,
        # with autoconnect DISABLED. The previous add-then-modify approach
        # left a window where NetworkManager could begin activating a
        # half-configured (open, no 802.1X) profile whenever the SSID was
        # in range - i.e. it only misbehaved on campus. Autoconnect is
        # enabled only after a successful 'up'.
        add_cmd = [
            'nmcli', 'connection', 'add',
            'type', 'wifi',
            'ifname', 'wlan0',
            'con-name', MANAGED_STA_CON_NAME,
            'ssid', ssid,
            'connection.autoconnect', 'no',
            'wifi-sec.key-mgmt', 'wpa-eap',
            '802-1x.eap', eap_method,
            '802-1x.identity', identity,
            '802-1x.password', password,
            '802-1x.phase2-auth', phase2
        ]

        # Add optional parameters if provided
        if anon_identity:
            add_cmd.extend(['802-1x.anonymous-identity', anon_identity])
        if ca_cert and os.path.exists(ca_cert):
            add_cmd.extend(['802-1x.ca-cert', ca_cert])
        elif ca_cert:
            logger.warning("CA cert configured but not found at %s, "
                           "connecting without server verification" % ca_cert)
        if domain_suffix_match:
            add_cmd.extend(['802-1x.domain-suffix-match', domain_suffix_match])
        if altsubject_match:
            add_cmd.extend(['802-1x.altsubject-matches', altsubject_match])

        result = subprocess.run(add_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            logger.error("Failed to create EAP connection: %s" % result.stderr.decode())
            return False

        # Bring up the connection
        result = subprocess.run(['nmcli', 'connection', 'up', MANAGED_STA_CON_NAME],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            logger.error("Failed to activate EAP connection: %s" % result.stderr.decode())
            return False

        enable_autoconnect()
        return True

    def WIFI_MGR():
        global WIFI_AP_SSID
        global WIFI_STA_SSID
        global WIFI_AP_PASSWORD
        global WIFI_STA_PASSWORD
        global led_on_time
        global led_off_time
        global server, ip
        
        if WIFI_MODE == 1: #AP
            logger.info("Starting AP mode with SSID: %s" % WIFI_AP_SSID)
            led_on_time = 50
            led_off_time = 50
            if type(WIFI_AP_PASSWORD) != str: #check password
                logger.error("Invalid WIFI_PASSWORD")
                WIFI_AP_PASSWORD = ""
            if len(WIFI_AP_PASSWORD) < 8 and WIFI_AP_PASSWORD != "":
                logger.error("password is too short")
                WIFI_AP_PASSWORD = ""
            if type(WIFI_AP_SSID) != str: #check ssid
                logger.error("Invalid WIFI_AP_SSID")
                WIFI_AP_SSID = ''.join([ap_prefix, sn[0:8]])

            # Safe disconnect - only managed connections
            disconnect_managed_only()
            subprocess.run(['nmcli', 'connection', 'down', WIFI_AP_SSID], stderr=subprocess.DEVNULL)
            subprocess.run(['nmcli', 'connection', 'delete', WIFI_AP_SSID], stderr=subprocess.DEVNULL)
            os.system('nmcli con add type wifi ifname wlan0 con-name {} autoconnect yes ssid {}'.format(WIFI_AP_SSID, WIFI_AP_SSID))
            os.system('nmcli con modify {} 802-11-wireless.mode ap ipv4.method shared'.format(WIFI_AP_SSID))
            os.system('nmcli con modify {} wifi-sec.key-mgmt wpa-psk wifi-sec.psk {}'.format(WIFI_AP_SSID, WIFI_AP_PASSWORD))
            os.system('nmcli con modify {} wifi.band {} wifi.channel {}'.format(WIFI_AP_SSID, WIFI_FREQ_BAND, WIFI_CHANNEL))
            os.system('nmcli con modify {} ipv4.addresses {}/24'.format(WIFI_AP_SSID, WIFI_AP_GATEWAY))
            timeout = 0
            while True:
                timeout += 1
                wifi = get_connect()
                if wifi == WIFI_AP_SSID:
                    logger.info("AP created successfully: %s" % WIFI_AP_SSID)
                    print("*************Create AP: " + WIFI_AP_SSID)
                    return -1
                if timeout == 20:
                    print("*************Restart NetworkManager")
                    os.system('systemctl restart NetworkManager')
                if timeout > 20:
                    logger.error("Failed to create AP after timeout")
                    print("*************Create Fail Restart ...")
                    return 0
                time.sleep(1)

        elif WIFI_MODE == 2: #Client/STA
            led_on_time = 5
            led_off_time = 5

            # Idempotency: if our managed connection is already active on
            # the configured SSID, leave it alone. Without this, every
            # service (re)start tears down a working connection and
            # rebuilds it from scratch.
            try:
                result = subprocess.run(
                    ['nmcli', '-t', '-f', 'NAME', 'con', 'show', '--active'],
                    stdout=subprocess.PIPE)
                if MANAGED_STA_CON_NAME in result.stdout.decode().split('\n'):
                    result = subprocess.run(
                        ['nmcli', '-g', '802-11-wireless.ssid',
                         'con', 'show', MANAGED_STA_CON_NAME],
                        stdout=subprocess.PIPE)
                    if result.stdout.decode().strip() == WIFI_STA_SSID:
                        msg = "Already connected to %s, nothing to do" % WIFI_STA_SSID
                        print("*************%s" % msg)
                        logger.info(msg)
                        led_on_time = 100
                        led_off_time = 0
                        return -1
            except Exception as e:
                logger.warning("Idempotency check failed, continuing: %s" % str(e))

            # Safe disconnect - only managed connections
            disconnect_managed_only()

            # Determine security type
            security = WIFI_STA_SECURITY.lower() if 'WIFI_STA_SECURITY' in globals() else 'psk'
            logger.info("STA mode: security=%s, SSID=%s" % (security, WIFI_STA_SSID))

            connect_success = False

            if security == "eap":
                # WPA2-Enterprise / 802.1X
                connect_success = connect_sta_eap(
                    ssid=WIFI_STA_SSID,
                    identity=WIFI_EAP_IDENTITY,
                    password=WIFI_EAP_PASSWORD,
                    anon_identity=WIFI_EAP_ANON_IDENTITY if 'WIFI_EAP_ANON_IDENTITY' in globals() else "",
                    ca_cert=WIFI_EAP_CA_CERT if 'WIFI_EAP_CA_CERT' in globals() else "",
                    eap_method=WIFI_EAP_METHOD if 'WIFI_EAP_METHOD' in globals() else "peap",
                    phase2=WIFI_EAP_PHASE2 if 'WIFI_EAP_PHASE2' in globals() else "mschapv2",
                    domain_suffix_match=WIFI_EAP_DOMAIN_SUFFIX_MATCH if 'WIFI_EAP_DOMAIN_SUFFIX_MATCH' in globals() else "",
                    altsubject_match=WIFI_EAP_ALTSUBJECT_MATCH if 'WIFI_EAP_ALTSUBJECT_MATCH' in globals() else ""
                )
            else:
                # WPA2-PSK (default, backward compatible)
                connect_success = connect_sta_psk(WIFI_STA_SSID, WIFI_STA_PASSWORD)

            if not connect_success:
                logger.error("Initial connection attempt failed for %s" % WIFI_STA_SSID)
                return 0

            # Wait for connection to be active
            count = 0
            while True:
                cmd = "nmcli -t -f ACTIVE,SSID dev wifi | grep 'yes' | cut -d\\: -f2"
                result = subprocess.check_output(cmd, shell=True)

                ssid_name = result.decode().strip()
                if count < WIFI_TIMEOUT and ssid_name == '':
                    count += 1
                    time.sleep(1)
                elif ssid_name == WIFI_STA_SSID:
                    msg = "Connected to " + WIFI_STA_SSID
                    print("*************%s"%msg)
                    logger.info(msg)
                    led_on_time = 100
                    led_off_time = 0
                    break
                else:
                    msg = "Can not connect to SSID: " + WIFI_STA_SSID
                    print("*************%s"%msg)
                    logger.error(msg)
                    return 0

            return -1
        else:
            logger.error("Invalid WIFI_MODE: %s" % WIFI_MODE)
            return 0
    if WIFI_LED == True:
        threading.Thread(target = led_thread).start()

    # Store original mode for fallback logic
    original_mode = WIFI_MODE

    while True:
        try:
            ret = WIFI_MGR()
        except BaseException as e:
            logger.error("Exception in WIFI_MGR: %s" % str(e))
            print('error', e)
            ret = 0

        if ret == -1:
            # Success - exit cleanly
            sys.exit(0)

        # Failure handling
        if original_mode == 2 and WIFI_FALLBACK_TO_AP:
            # STA failed and fallback is enabled - switch to AP mode
            logger.warning("STA connection failed, falling back to AP mode")
            WIFI_MODE = 1
            original_mode = 1  # Prevent repeated fallback attempts
        else:
            # No fallback configured - retry same mode after delay
            logger.info("Retrying WIFI_MODE=%s after failure" % WIFI_MODE)
            time.sleep(5)
