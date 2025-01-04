# LuckFox Pico SD Card Flashing Tools

A set of tools for efficient flashing of LuckFox Pico Pro/Max SD cards, with support for multiple card operations and optimized writing performance.

## Tools Included

### 1. img2sd
Primary tool for flashing SD cards based on `.env.txt` configuration.

### 2. multiflash
Tool for managing multiple SD card flashing operations simultaneously.

## Prerequisites

- Python 3.6 or higher
- Linux-based operating system
- Root privileges (sudo)
- Required Python packages: None (uses standard library only)

## Installation

1. Clone or download the repository:
```bash
git clone https://github.com/tom-sapletta-com/luckfox.git
cd luckfox-flash-tools
```

2. Make scripts executable:
```bash
chmod +x img2sd
chmod +x multiflash.py
```

## Usage

### Single Card Flashing (img2sd)

1. Interactive Mode (Recommended):
```bash
sudo ./img2sd
```
- Shows available devices
- Allows selection using arrow keys or numbers
- Validates device selection
- Shows progress and verification status

2. Direct Device Specification:
```bash
sudo ./img2sd /dev/sdX
```

### Multiple Card Flashing (multiflash)

1. Start the monitoring tool:
```bash
sudo ./multiflash.py
```
- Automatically detects inserted SD cards
- Manages concurrent flashing operations
- Shows real-time status updates

## Features

### img2sd

- Interactive device selection
- Safe device validation
- Progress monitoring
- Optimized writing for large files
- Data verification
- Support for partitioned images

#### Performance Optimizations

1. Large Block Sizes
   - Uses 64MB blocks for large files
   - 1MB blocks for smaller files
   - Optimized for modern SD cards

2. Efficient Verification
   - Quick verification for large files (>64MB)
   - Full verification for small files
   - Sampling-based verification option

3. Progress Monitoring
   - Real-time write speed
   - Estimated time remaining
   - Clear status updates

### multiflash

- Automatic device detection
- Concurrent operations
- Status monitoring
- Safe device removal handling
- Error recovery

## Configuration

### Environment Variables

- `SKIP_VERIFY=1`: Skip verification phase (faster but less safe)
- `BLOCK_SIZE=XM`: Override default block size (default: 64M for large files)

### Performance Tuning

For optimal performance:

1. Enable write caching:
```bash
sudo hdparm -W 1 /dev/sdX
```

2. Increase system buffer:
```bash
sudo sysctl -w vm.dirty_ratio=60
sudo sysctl -w vm.dirty_background_ratio=30
```

## Troubleshooting

### Common Issues

1. Permission Denied
```bash
sudo chmod +x img2sd multiflash.py
```

2. Device Busy
```bash
sudo umount /dev/sdX*
```

3. Verification Failures
- Check if the SD card is properly inserted
- Try with a lower block size
- Check for card errors with `badblocks`

### Error Messages

1. "Device validation failed":
   - Ensure the device is removable
   - Check device permissions
   - Verify device path

2. "Write failed":
   - Check available space
   - Verify card is not write-protected
   - Check for filesystem errors

## Performance Tips

1. Use high-quality SD cards
2. Enable write caching when possible
3. Close unnecessary applications
4. Use USB 3.0 ports when available
5. Consider disabling verification for trusted images

## Safety Features

1. Device Validation
   - Checks for removable media
   - Prevents system disk writes
   - Validates device paths

2. Data Verification
   - Checksum verification
   - Partition size validation
   - Write confirmation

3. Error Handling
   - Graceful error recovery
   - Clear error messages
   - Safe cleanup operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

+ [LICENSE](LICENSE)


## Authors

+ Tom Sapletta <info@softreck.dev>

## Version History

- 0.0.2
  - Added performance optimizations
  - Added verifications
  - Improved device selection
  - Added multiflash tool

- 0.0.1
  - Initial release
  
