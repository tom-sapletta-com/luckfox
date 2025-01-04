#!/usr/bin/python3

# == MULTIFLASH == written by Tom Sapletta <info@softreck.dev>
#
# Description:
#    Automates the process of flashing multiple SD cards using img2sd
#    Detects newly inserted SD cards and manages concurrent flashing operations
#
# Usage:
#    % sudo ./multiflash.py
#
# License: MIT

import os
import sys
import time
import json
import subprocess
import threading
from typing import Dict, List, Set
from datetime import datetime
from queue import Queue

class SDCardMonitor:
    def __init__(self):
        self.known_devices: Set[str] = set()
        self.active_devices: Set[str] = set()
        self.completed_devices: Set[str] = set()
        self.failed_devices: Set[str] = set()
        self.lock = threading.Lock()
        self.flash_queue = Queue()
        self.stop_event = threading.Event()

    def get_sd_cards(self) -> List[Dict[str, str]]:
        """Get list of SD cards from system."""
        try:
            cmd = ['lsblk', '-d', '-o', 'NAME,SIZE,TYPE,MODEL,RM', '--json']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Filter for removable devices (SD cards)
            sd_cards = []
            for device in data.get('blockdevices', []):
                if (device.get('type') == 'disk' and 
                    device.get('rm') == '1' and  # Removable media
                    not device['name'].startswith('zram')):
                    sd_cards.append(device)
            
            return sd_cards
        except Exception as e:
            print(f"Error getting SD card list: {e}")
            return []

    def start_flash_worker(self):
        """Worker thread to process flash queue."""
        while not self.stop_event.is_set():
            try:
                device = self.flash_queue.get(timeout=1)
                if device:
                    self.flash_device(device)
            except Queue.Empty:
                continue
            except Exception as e:
                print(f"Worker error: {e}")

    def flash_device(self, device: str):
        """Flash a single device using img2sd."""
        try:
            with self.lock:
                if device in self.active_devices:
                    return
                self.active_devices.add(device)

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting flash of {device}...")
            
            # Run img2sd
            cmd = ['./img2sd', device]
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            with self.lock:
                self.active_devices.remove(device)
                if process.returncode == 0:
                    self.completed_devices.add(device)
                    print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] Successfully flashed {device}")
                else:
                    self.failed_devices.add(device)
                    print(f"✗ [{datetime.now().strftime('%H:%M:%S')}] Failed to flash {device}")
                    print(f"Error output:\n{process.stderr}")

        except Exception as e:
            print(f"Error flashing {device}: {e}")
            with self.lock:
                self.active_devices.remove(device)
                self.failed_devices.add(device)

    def print_status(self):
        """Print current status of all devices."""
        print("\nCurrent Status:")
        print("=" * 50)
        print(f"Active devices: {', '.join(self.active_devices) if self.active_devices else 'None'}")
        print(f"Completed devices: {', '.join(self.completed_devices) if self.completed_devices else 'None'}")
        print(f"Failed devices: {', '.join(self.failed_devices) if self.failed_devices else 'None'}")
        print("=" * 50)

    def monitor_sd_cards(self):
        """Main monitoring loop for SD cards."""
        print("Starting SD card monitor. Insert SD cards to begin flashing.")
        print("Press Ctrl+C to stop.")
        
        # Start worker thread
        worker = threading.Thread(target=self.start_flash_worker)
        worker.daemon = True
        worker.start()

        try:
            while True:
                current_devices = {f"/dev/{dev['name']}" for dev in self.get_sd_cards()}
                
                # Check for new devices
                new_devices = current_devices - self.known_devices
                for device in new_devices:
                    print(f"\nNew SD card detected: {device}")
                    self.known_devices.add(device)
                    if device not in self.completed_devices and device not in self.failed_devices:
                        self.flash_queue.put(device)

                # Check for removed devices
                removed_devices = self.known_devices - current_devices
                for device in removed_devices:
                    print(f"\nSD card removed: {device}")
                    self.known_devices.remove(device)
                    if device in self.completed_devices:
                        self.completed_devices.remove(device)
                    if device in self.failed_devices:
                        self.failed_devices.remove(device)

                self.print_status()
                time.sleep(2)  # Check every 2 seconds

        except KeyboardInterrupt:
            print("\nStopping monitor...")
            self.stop_event.set()
            worker.join()
            print("\nFinal status:")
            self.print_status()

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root (sudo)!")
        sys.exit(1)
        
    if not os.path.exists('./img2sd'):
        print("Error: img2sd script not found in current directory!")
        sys.exit(1)
        
    monitor = SDCardMonitor()
    monitor.monitor_sd_cards()
