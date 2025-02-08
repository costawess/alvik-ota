import network
import urequests
import os
import machine
from time import sleep

class OTAUpdater:
    """Handles OTA updates by downloading and comparing the latest firmware file."""
    
    def __init__(self, ssid, password, repo_url, filename="main.py"):
        self.filename = filename
        self.ssid = ssid
        self.password = password
        self.repo_url = repo_url

        # Convert GitHub repo URL to raw content URL
        if "github.com" in self.repo_url:
            print(f"Updating {repo_url} to raw.githubusercontent.com")
            self.repo_url = self.repo_url.replace("github.com", "raw.githubusercontent.com")

        self.firmware_url = self.repo_url + 'main/' + filename
        print(f"✅Complete Firmware URL: {self.firmware_url}")

    def connect_wifi(self):
        """ Connects to Wi-Fi. """
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        sta_if.connect(self.ssid, self.password)
        
        print("Connecting to WiFi...", end="")
        while not sta_if.isconnected():
            print(".", end="")
            sleep(0.5)
        
        print(f"\n✅ Connected to WiFi, IP: {sta_if.ifconfig()[0]}")

    def fetch_latest_code(self):
        """ Fetches the latest firmware file and returns its content. """
        try:
            response = urequests.get(self.firmware_url)
            if response.status_code == 200:
                print(f"✅ Fetched latest firmware ({self.filename}), size: {len(response.text)} bytes")
                latest_code = response.text
                response.close()
                return latest_code
            else:
                print(f"❌ Failed to fetch firmware. HTTP {response.status_code}")
                response.close()
                return None
        except Exception as e:
            print(f"⚠ Error fetching firmware: {e}")
            return None

    def get_current_code(self):
        """ Reads the current firmware file if it exists. """
        if self.filename in os.listdir():
            with open(self.filename, "r") as f:
                return f.read()
        return ""

    def update_and_reset(self, new_code):
        """ Updates the firmware file and resets the device. """
        print("⚡ Updating firmware...")

        # mantem a versao antiga
        old_filename = self.filename.rsplit('.', 1)[0] + "_OLD_VERSION." + self.filename.rsplit('.', 1)[1]
        if self.filename in os.listdir():
            os.rename(self.filename, old_filename)
        
        # escreve a nova versao
        with open(self.filename, "w") as f:
            f.write(new_code)

        print("✅ Update complete! Restarting...")
        machine.reset()  # Reset to apply the new firmware

    def check_for_updates(self):
        """ Downloads the latest firmware and compares it with the current version. """
        print("🔍 Checking for firmware updates...")

        latest_code = self.fetch_latest_code()
        if latest_code is None:
            print("🚫 No update available or failed to fetch the latest firmware.")
            return False
        
        current_code = self.get_current_code()

        print("latest_code: ", latest_code)

        print("-------------------")

        print("current_code: ", current_code)
        
        if latest_code.strip() == current_code.strip():
            print("✅ Firmware is already up to date. No changes detected.")
            return False
        else:
            print("🆕 New firmware detected! Updating now...")
            
            self.update_and_reset(latest_code)
            return True

    def download_and_install_update_if_available(self):
        """ Main function to handle OTA update. """
        self.connect_wifi()
        return self.check_for_updates()
