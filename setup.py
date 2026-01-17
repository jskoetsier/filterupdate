#!/usr/bin/env python3
"""
Modern setup script for filterupdate tool using setuptools.
"""

import argparse
import platform
import subprocess
import sys

def check_python_version() -> None:
    """Check if Python version is 3.8 or higher."""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required.")
        sys.exit(1)
    print(f"✓ Python version: {sys.version.split()[0]}")

def install_python_packages(lite: bool = False) -> None:
    """Install required Python packages using pip."""
    print("\nInstalling required Python packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

        common_packages = ["paramiko>=3.0.0", "scp>=0.14.0"]
        if not lite:
            common_packages.append("netmiko>=5.0.0")

        for package in common_packages:
            try:
                print(f"Installing {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            except subprocess.CalledProcessError as e:
                print(f"Warning: Error installing {package}: {e}")
                print("Continuing with installation...")

        print("✓ Successfully installed Python packages")
        print("\nNote: If you encounter any issues with the dependencies, you can try:")
        print("  pip install -r requirements.txt")
    except Exception as exc:
        print(f"Error during package installation: {exc}")
        print("\nAlternative installation method:")
        print("  pip install -r requirements.txt")

def check_bgpq4() -> None:
    """Check if bgpq4 is installed and provide installation instructions if not."""
    print("\nChecking for bgpq4...")
    try:
        subprocess.check_call(
            ["which", "bgpq4"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✓ bgpq4 is installed")
    except subprocess.CalledProcessError:
        print("✗ bgpq4 is not installed")
        system = platform.system()

        print("\nInstallation instructions for bgpq4:")
        if system == "Darwin":  # macOS
            print(
                """
On macOS:
    Using Homebrew: brew install bgpq4
    Using MacPorts: sudo port install bgpq4
                """
            )
        elif system == "Linux":
            print(
                """
On Linux:
    Debian/Ubuntu: sudo apt-get install bgpq4
    CentOS/RHEL:
        1. Install EPEL repository if not already installed:
            sudo yum install epel-release
        2. Install bgpq4:
            sudo yum install bgpq4

     Alternatively, install from source:
     git clone https://github.com/bgp/bgpq4.git
     cd bgpq4
     ./configure
     make
     sudo make install
                """
            )
        else:
            print(
                """
Please install bgpq4 from source:
    git clone https://github.com/bgp/bgpq4.git
    cd bgpq4
    ./configure
    make
    sudo make install
                """
            )

def main() -> None:
    """Main function to run the setup."""
    parser = argparse.ArgumentParser(description="Setup script for filterupdate tool")
    parser.add_argument(
        "--lite",
        action="store_true",
        help="Setup for lightweight version (no device connection)",
    )
    args = parser.parse_args()

    print("Setting up filterupdate tool...\n")

    check_python_version()

    install_python_packages(lite=args.lite)

    if not args.lite:
        check_bgpq4()

    if args.lite:
        print(
            "\nSetup complete for lightweight version! You can now use the filterupdate_lite.py script."
        )
        print("Run 'python3 filterupdate_lite.py -h' for usage instructions.")
        print(
            "\nNote: The lightweight version only generates configurations without applying them."
        )
    else:
        print("\nSetup complete! You can now use the filterupdate.py script.")
        print("Run 'python3 filterupdate.py -h' for usage instructions.")
        print(
            "\nNote: This version uses Netmiko for device connections and is compatible with Python 3.12."
        )


if __name__ == "__main__":
    main()
