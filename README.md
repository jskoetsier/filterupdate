# Filterupdate

A Python tool for automatic BGP prefix filter updates on Juniper devices. This tool uses bgpq3 to generate prefix lists from IRR databases and applies them to Juniper devices using the PyEZ library.

## Requirements

- Python 3.6 or higher
- bgpq3 command-line tool
- Juniper PyEZ library

## Installation

### Option 1: Using the setup script

The easiest way to install the required dependencies is to use the provided setup script:

```bash
python3 setup.py
```

This script will:
- Check your Python version
- Install the required Python packages
- Check if bgpq3 is installed and provide installation instructions if needed

### Option 2: Manual installation

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

2. Install bgpq3:

   - On macOS:
     ```bash
     brew install bgpq3
     ```
     or
     ```bash
     sudo port install bgpq3
     ```

   - On Debian/Ubuntu:
     ```bash
     sudo apt-get install bgpq3
     ```

   - On CentOS/RHEL:
     ```bash
     sudo yum install epel-release
     sudo yum install bgpq3
     ```

   - From source:
     ```bash
     git clone https://github.com/snar/bgpq3.git
     cd bgpq3
     ./configure
     make
     sudo make install
     ```

## Usage

```bash
python3 filterupdate.py -d <device> -a <as-set> -l <prefix-list-name> [-6]
```

### Parameters:

- `-d`: Juniper device hostname or IP address
- `-a`: AS-SET to create prefix list from (e.g., AS-EXAMPLE)
- `-l`: Name of the prefix list to create/update
- `-6`: (Optional) Use IPv6 instead of IPv4

### Example:

```bash
python3 filterupdate.py -d router.example.com -a AS-EXAMPLE -l customer-prefixes
```

For IPv6:

```bash
python3 filterupdate.py -d router.example.com -a AS-EXAMPLE -l customer-prefixes-v6 -6
```

## How it works

1. The tool uses bgpq3 to query the IRR database (rr.ntt.net) for prefixes associated with the specified AS-SET
2. It generates a Juniper-compatible prefix list configuration
3. It connects to the specified Juniper device using PyEZ
4. It loads and commits the configuration, replacing the existing prefix list

## License

This project is licensed under the MIT License - see the [license.txt](license.txt) file for details.

## Author

(c) 2019 - Sebastiaan Koetsier
