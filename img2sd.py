#    Writes an image (.img) or to the SD card direct from existing .env.txt for LuckFox Pico Pro/Max
#    With added safety features:
#    - Disk selection validation
#    - Image verification after writing
#    - Size validation
#    - Interactive disk selection
#
#       % ./img2sd disk.img
#       -- inquery with `lsblk` which device is your SD card resides --
#       % sudo dd if=disk.img of=/dev/sdX bs=1M; sync
#
#       -- or do in one step -- 
#       % sudo ./img2sd /dev/sdX
#
#     images: https://drive.google.com/drive/folders/1r6Ulc_crJar1entKbK7GEJSq14HXL8ao

import os
import sys
import re
import subprocess
import shutil
import atexit
import hashlib
from typing import Dict, List, Tuple, Optional

VERSION = '0.0.1'

def get_disk_info() -> List[Dict[str, str]]:
    """Get information about available disks using lsblk."""
    try:
        cmd = ['lsblk', '-d', '-o', 'NAME,SIZE,TYPE,MODEL', '--json']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        data = json.loads(result.stdout)
        
        # Validate the data structure
        if not isinstance(data, dict) or 'blockdevices' not in data:
            print("Warning: Unexpected lsblk output format")
            return []
            
        devices = data['blockdevices']
        if not isinstance(devices, list):
            print("Warning: Invalid block devices data")
            return []
            
        # Filter out any invalid entries
        valid_devices = []
        for device in devices:
            if isinstance(device, dict) and 'name' in device and 'type' in device:
                valid_devices.append(device)
            else:
                print(f"Warning: Skipping invalid device entry: {device}")
                
        return valid_devices
    except subprocess.CalledProcessError as e:
        print(f"Error running lsblk command: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing lsblk output: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error getting disk information: {e}")
        return []

def is_removable(device: str) -> bool:
    """Check if the device is removable (like SD cards)."""
    try:
        with open(f"/sys/block/{os.path.basename(device)}/removable") as f:
            return f.read().strip() == "1"
    except:
        return False

def validate_device(device: str) -> bool:
    """Validate if the selected device is safe to write to."""
    if not device.startswith('/dev/'):
        return False
    
    device_name = os.path.basename(device)
    
    # Get disk information
    disks = get_disk_info()
    
    # Find the selected device in the disk list
    selected_disk = next((d for d in disks if d['name'] == device_name), None)
    if not selected_disk:
        return False
    
    # Check if it's a removable device
    if not is_removable(device):
        print(f"WARNING: {device} does not appear to be removable!")
        confirm = input("Are you absolutely sure you want to continue? (yes/NO): ")
        return confirm.lower() == 'yes'
    
    return True

def calculate_checksum(file_path: str, chunk_size: int = 8192) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def verify_written_data(source_file: str, device: str, offset: int, size: int) -> bool:
    """Verify written data by comparing checksums."""
    print(f"Verifying written data for {source_file}...")
    
    # Get actual file size
    actual_size = os.path.getsize(source_file)
    
    # Calculate source checksum
    source_checksum = calculate_checksum(source_file)
    
    # Read written data and calculate checksum
    try:
        # Use actual file size for verification, not partition size
        cmd = ['dd', f"if={device}", f"skip={offset//1024}", f"count={actual_size//1024}", 'bs=1k']
        if actual_size % 1024:  # Handle files that aren't exact multiples of 1K
            cmd.extend(['iflag=count_bytes'])
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: proc.stdout.read(8192), b''):
            sha256.update(chunk)
        written_checksum = sha256.hexdigest()
        
        return source_checksum == written_checksum
    except Exception as e:
        print(f"Error during verification: {e}")
        return False

def true_size(s: str) -> int:
    """Convert size string to bytes."""
    u = {'B': 1, 'K': 1024, 'M': 1024*1024, 'G': 1024*1024*1024}
    if m := re.search(r'(\d+)([BKMG])', s):
        return int(m.group(1)) * u[m.group(2)]
    return 0

def nice_size(n: int) -> str:
    """Convert bytes to human-readable format."""
    u = {'B': 1, 'K': 1024, 'M': 1024*1024, 'G': 1024*1024*1024}
    for k, v in reversed(u.items()):
        if n >= v and n % v == 0:
            return f"{n//v:,}{k}"
    return f"{n:,}B"

def cleanup():
    """Cleanup function to restore original env file if needed."""
    if os.path.exists(".env.txt.orig"):
        os.rename(".env.txt.orig", ".env.txt")
    print("Cleanup done.")

def select_device() -> Optional[str]:
    """Interactive device selection with arrow keys."""
    import curses

    def setup_menu(stdscr, devices):
        curses.curs_set(0)  # Hide cursor
        stdscr.clear()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        return stdscr, devices

    def draw_menu(stdscr, devices, selected_idx):
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        # Draw header
        header = "Available devices:"
        stdscr.addstr(0, 0, "=" * w)
        stdscr.addstr(1, 0, header)
        stdscr.addstr(2, 0, "=" * w)
        stdscr.addstr(3, 0, f"{'#':4} {'Device':12} {'Size':10} {'Type':10} {'Model':30}")
        stdscr.addstr(4, 0, "-" * w)

        # Draw devices
        for idx, disk in enumerate(devices):
            if disk['type'] == 'disk':
                model = disk.get('model') or 'N/A'
                name = str(disk.get('name', ''))
                size = str(disk.get('size', '0B'))
                disk_type = str(disk.get('type', 'unknown'))
                
                y = idx + 5
                if y < h:
                    if idx == selected_idx:
                        stdscr.attron(curses.color_pair(1))
                        stdscr.addstr(y, 0, f"{idx + 1:3}) /dev/{name:12} {size:10} {disk_type:10} {model:30}")
                        stdscr.attroff(curses.color_pair(1))
                    else:
                        stdscr.addstr(y, 0, f"{idx + 1:3}) /dev/{name:12} {size:10} {disk_type:10} {model:30}")

        # Draw footer
        footer_y = min(h - 2, len(devices) + 6)
        stdscr.addstr(footer_y, 0, "-" * w)
        stdscr.addstr(footer_y + 1, 0, "Use ↑↓ arrows to select, Enter to confirm, 'q' to quit")
        
        stdscr.refresh()

    def menu_loop(stdscr):
        disks = get_disk_info()
        valid_disks = [d for d in disks if d['type'] == 'disk']
        
        if not valid_disks:
            return None

        stdscr, devices = setup_menu(stdscr, valid_disks)
        selected_idx = 0
        
        while True:
            draw_menu(stdscr, valid_disks, selected_idx)
            
            key = stdscr.getch()
            
            if key == curses.KEY_UP and selected_idx > 0:
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < len(valid_disks) - 1:
                selected_idx += 1
            elif key in [ord('\n'), ord('\r')]:  # Enter key
                return f"/dev/{valid_disks[selected_idx]['name']}"
            elif key in [ord('q'), ord('Q')]:  # Quit
                return None
            # Number key selection
            elif 49 <= key <= 57:  # 1-9
                idx = key - 49  # Convert to 0-based index
                if idx < len(valid_disks):
                    return f"/dev/{valid_disks[idx]['name']}"

    try:
        selected_device = curses.wrapper(menu_loop)
        
        if selected_device:
            print(f"\nSelected device: {selected_device}")
            if not validate_device(selected_device):
                print("Device validation failed! Please select a different device.")
                return None
            return selected_device
        
        return None
        
    except KeyboardInterrupt:
        print("\nDevice selection cancelled.")
        return None

def quick_verify_data(source_file: str, device: str, offset: int, size: int) -> bool:
    """Quick verification by sampling data at different positions."""
    SAMPLE_SIZE = 1024 * 1024  # 1MB samples
    file_size = os.path.getsize(source_file)
    
    # Take samples at start, middle and end
    positions = [
        0,  # Start
        file_size // 2,  # Middle
        max(0, file_size - SAMPLE_SIZE)  # End
    ]
    
    try:
        for pos in positions:
            # Read sample from source file
            with open(source_file, 'rb') as f:
                f.seek(pos)
                source_sample = f.read(SAMPLE_SIZE)
                
            # Read sample from device
            cmd = [
                'dd',
                f"if={device}",
                f"skip={(offset + pos)//1024}",
                f"count={SAMPLE_SIZE//1024}",
                'bs=1k',
                'iflag=skip_bytes,count_bytes'
            ]
            proc = subprocess.run(cmd, capture_output=True)
            device_sample = proc.stdout
            
            if source_sample != device_sample:
                return False
                
        return True
    except Exception as e:
        print(f"Error during quick verification: {e}")
        return False#!/usr/bin/python3
        
def main():
    """Main function."""
    me = os.path.basename(sys.argv[0])
    path = os.path.dirname(sys.argv[0])

    # Default to interactive mode if no arguments provided
    if len(sys.argv) == 1:
        dev = select_device()
        if not dev:
            print("No valid device selected. Exiting.")
            sys.exit(1)
    # Allow manual device specification for scripting/automation
    elif len(sys.argv) == 2:
        dev = sys.argv[1]
        # Still allow explicit selection mode
        if dev == "select":
            dev = select_device()
            if not dev:
                print("No valid device selected. Exiting.")
                sys.exit(1)
    else:
        print(f"""USAGE: {me} [device]
        examples:
           % ./{me}              # Interactive mode (recommended)
           % ./{me} /dev/sdX     # Direct device specification
        """)
        sys.exit(-1)
    
    print(f"== {me} {VERSION} ==")
    
    # Validate device before proceeding
    if dev.startswith('/dev/'):
        if not validate_device(dev):
            print("Device validation failed! Exiting for safety.")
            sys.exit(1)
    
    print(f"Writing to {dev}")

    # Register cleanup handler
    atexit.register(cleanup)
    
    with open(".env.txt") as fh:
        env2 = []
        for l in fh.readlines():
            if m := re.search(r'(blkdevparts|sd_parts)=(\w+)', l):
                _type = m.group(1)
                _dev = m.group(2)
                l = re.sub(r'blkdevparts=\w+:', '', l)
                p = l.split(',')
                c_off = 0
                
                if _dev == 'mmcblk1':
                    for e in p:
                        if (m := re.search(r'(\d+[KMG])@(\d+[KMG])\((\w+)\)', e)) or (m := re.search(r'(\d+[KMG])\((\w+)\)', e)):
                            if len(m.groups()) == 3:
                                size = true_size(m.group(1))
                                off = true_size(m.group(2))
                                name = m.group(3)
                            else:
                                size = true_size(m.group(1))
                                name = m.group(2)
                                off = 0

                            print(f"   {_dev}: {name}.img size:{size:,}/{nice_size(size)} (offset:{off:,}/{nice_size(off)})", end='')
                            
                            img_path = f"{name}.img"
                            if os.path.exists(img_path):
                                size_ = os.path.getsize(img_path)
                                print(f" imgsize:{size_:,} ({nice_size(size_)})")
                                
                                # Write the image with optimized parameters
                                actual_size = os.path.getsize(img_path)
                                if actual_size > size:
                                    print(f"Warning: Image size ({nice_size(actual_size)}) exceeds partition size ({nice_size(size)})")
                                    sys.exit(1)
                                
                                # Calculate optimal block size (using 64MB blocks for large files)
                                block_size = "64M" if actual_size > 64*1024*1024 else "1M"
                                
                                # Optimize dd parameters for speed
                                cmd = [
                                    'dd',
                                    f"if={img_path}",
                                    f"of={dev}",
                                    f"bs={block_size}",
                                    f"seek={c_off//(64*1024*1024 if block_size=='64M' else 1024*1024)}",
                                    'conv=fdatasync',
                                    'iflag=fullblock',
                                    'status=progress'
                                ]
                                
                                try:
                                    print(f"Writing {img_path} (using {block_size} blocks)...")
                                    # Use direct subprocess call to show progress
                                    process = subprocess.Popen(
                                        cmd, 
                                        stderr=subprocess.PIPE, 
                                        universal_newlines=True
                                    )
                                    while True:
                                        output = process.stderr.readline()
                                        if output == '' and process.poll() is not None:
                                            break
                                        if output:
                                            print(output.strip(), end='\r')
                                    print() # New line after progress
                                    
                                    # Only pad if really necessary
                                    if actual_size < size:
                                        pad_size = size - actual_size
                                        # Use same optimized block size for padding
                                        print(f"Padding with zeros ({nice_size(pad_size)})...")
                                        pad_cmd = [
                                            'dd',
                                            'if=/dev/zero',
                                            f"of={dev}",
                                            f"bs={block_size}",
                                            f"seek={(c_off + actual_size)//(64*1024*1024 if block_size=='64M' else 1024*1024)}",
                                            f"count={pad_size//(64*1024*1024 if block_size=='64M' else 1024*1024)}",
                                            'conv=fdatasync'
                                        ]
                                        subprocess.run(pad_cmd, check=True, capture_output=True)
                                    
                                    # Quick verification for large files
                                    if actual_size > 64*1024*1024:  # 64MB
                                        print("Performing quick verification (sampling)...")
                                        if quick_verify_data(img_path, dev, c_off, size):
                                            print(f"✓ Quick verification successful for {img_path}")
                                        else:
                                            print(f"✗ Quick verification failed for {img_path}")
                                            confirm = input("Continue anyway? (yes/NO): ")
                                            if confirm.lower() != 'yes':
                                                sys.exit(1)
                                    else:
                                        # Full verification for smaller files
                                        if verify_written_data(img_path, dev, c_off, size):
                                            print(f"✓ Verification successful for {img_path}")
                                        else:
                                            if actual_size < size:
                                                print(f"ℹ Verification skipped - partition is padded ({nice_size(actual_size)} + {nice_size(pad_size)} padding)")
                                            else:
                                                print(f"✗ Verification failed for {img_path}")
                                                confirm = input("Continue anyway? (yes/NO): ")
                                                if confirm.lower() != 'yes':
                                                    sys.exit(1)
                                        
                                except subprocess.CalledProcessError as e:
                                    print(f"ERROR: {e}")
                                    sys.exit(1)
                                
                                c_off += size
                            else:
                                print(f"\nERROR: '{img_path}' not found")
                                sys.exit(1)
                
                if _dev == 'mmcblk0':
                    env2.append(l)

    # Sync to ensure all writes are completed
    subprocess.run(['sync'])
    print("\nAll operations completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
