# Filterupdate

A Python tool for automatic BGP prefix filter updates on Juniper devices. This tool queries IRR databases for prefixes associated with AS-SETs and applies them to Juniper devices.

## Requirements

- Python 3.6 or higher (Python 3.12 compatible)
- Netmiko library for device connections
- (Optional) bgpq4 command-line tool for more robust IRR queries

## Installation

### Option 1: Using the setup script

The easiest way to install the required dependencies is to use the provided setup script:

```bash
python3 setup.py
```

For the lightweight version (no device connection):
```bash
python3 setup.py --lite
```

This script will:
- Check your Python version
- Install the required Python packages
- Check if bgpq4 is installed and provide installation instructions if needed

### Option 2: Manual installation

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

2. (Optional) Install bgpq4 if you want to use the `--use-bgpq4` option:

   - On macOS:
     ```bash
     brew install bgpq4
     ```
     or
     ```bash
     sudo port install bgpq4
     ```

   - On Debian/Ubuntu:
     ```bash
     sudo apt-get install bgpq4
     ```

   - On CentOS/RHEL:
     ```bash
     sudo yum install epel-release
     sudo yum install bgpq4
     ```

   - From source:
     ```bash
     git clone https://github.com/bgp/bgpq4.git
     cd bgpq4
     ./configure
     make
     sudo make install
     ```

## Usage

### Main Version

```bash
python3 filterupdate.py -d <device> -u <username> -p <password> -a <as-set> -l <prefix-list-name> [-6] [-s <irr-server>] [--port <port>] [--use-bgpq4] [--test]
```

### Lightweight Version (no device connection)

```bash
python3 filterupdate_lite.py -a <as-set> -l <prefix-list-name> [-6] [-s <irr-server>] [--use-bgpq4] [-o <output-file>]
```

### Parameters:

#### For Main Version:
- `-d`: Juniper device hostname or IP address
- `-u`: Username for device login
- `-p`: Password for device login
- `-a`: AS-SET to create prefix list from (e.g., AS-EXAMPLE)
- `-l`: Name of the prefix list to create/update
- `-6`: (Optional) Use IPv6 instead of IPv4
- `-s`: (Optional) IRR server to query (default: rr.ntt.net)
- `--port`: (Optional) SSH port (default: 22)
- `--use-bgpq4`: (Optional) Use bgpq4 instead of direct IRR query
- `--test`: (Optional) Test mode: output configuration to stderr without applying to device

#### For Lightweight Version:
- `-a`: AS-SET to create prefix list from (e.g., AS-EXAMPLE)
- `-l`: Name of the prefix list to create/update
- `-6`: (Optional) Use IPv6 instead of IPv4
- `-s`: (Optional) IRR server to query (default: rr.ntt.net)
- `--use-bgpq4`: (Optional) Use bgpq4 instead of direct IRR query
- `-o`: (Optional) Output file (default: stdout)

### Example:

```bash
python3 filterupdate.py -d router.example.com -u admin -p password -a AS-EXAMPLE -l customer-prefixes
```

For IPv6:

```bash
python3 filterupdate.py -d router.example.com -u admin -p password -a AS-EXAMPLE -l customer-prefixes-v6 -6
```

Using bgpq4:

```bash
python3 filterupdate.py -d router.example.com -u admin -p password -a AS-EXAMPLE -l customer-prefixes --use-bgpq4
```

Test mode (outputs to stderr without applying to device):

```bash
python3 filterupdate.py -d router.example.com -u admin -p password -a AS-EXAMPLE -l customer-prefixes --test
```

Using the lightweight version:

```bash
python3 filterupdate_lite.py -a AS-EXAMPLE -l customer-prefixes -o config.txt
```

## How it works

### Main Version
1. The tool can either:
   - Directly query the IRR database using a socket connection (default)
   - Use bgpq4 if the `--use-bgpq4` option is specified
2. It parses the response to extract prefixes associated with the specified AS-SET
3. It generates a Juniper-compatible prefix list configuration
4. In test mode (`--test`), it outputs the configuration to stderr and exits
5. In normal mode, it connects to the specified Juniper device using Netmiko
6. It loads and commits the configuration, replacing the existing prefix list

### Lightweight Version
1. The tool can either:
   - Directly query the IRR database using a socket connection (default)
   - Use bgpq4 if the `--use-bgpq4` option is specified
2. It parses the response to extract prefixes associated with the specified AS-SET
3. It generates a Juniper-compatible prefix list configuration
4. It outputs the configuration to stdout or a specified file
5. It does NOT connect to any device or apply the configuration

## Version Comparison

| Feature | Main Version | Lightweight Version |
|---------|-------------|---------------------|
| External Dependencies | Optional (can use bgpq4 or not) | Optional (can use bgpq4 or not) |
| Device Library | Netmiko | None |
| Python 3.12 Compatible | Yes | Yes |
| Authentication | Username/password | N/A |
| IRR Query Method | Direct socket connection or bgpq4 | Direct socket connection or bgpq4 |
| Query Robustness | Basic or bgpq4 | Basic or bgpq4 |
| Test Capability | Yes | Always (generates config only) |

## License

This project is licensed under the MIT License - see the [license.txt](license.txt) file for details.

## Author

(c) 2019 - Sebastiaan Koetsier
