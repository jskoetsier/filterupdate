#!/usr/bin/env python3
"""
Setup script for filterupdate tool.
This script installs the required Python packages and optionally checks for the bgpq4 command-line tool.
"""

import argparse
import os
import platform
import subprocess
import sys


def check_python_version():
    """Check if Python version is 3.6 or higher."""
    if sys.version_info < (3, 6):
        print("Error: Python 3.6 or higher is required.")
        sys.exit(1)
    print(f"✓ Python version: {sys.version.split()[0]}")


def install_python_packages(lite=False):
    """Install required Python packages based on the selected version."""
    print("\nInstalling required Python packages...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
        )

        # Common packages for all versions
        common_packages = [
            "paramiko>=2.7.0",
            "scp>=0.13.0",
        ]

        # Version-specific packages
        if lite:
            specific_packages = []
            print("Installing minimal packages for lightweight version...")
        else:
            specific_packages = [
                "netmiko>=4.0.0",
            ]
            print("Installing packages for main version...")

        # Install all required packages
        packages = common_packages + specific_packages

        for package in packages:
            try:
                print(f"Installing {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            except subprocess.CalledProcessError as e:
                print(f"Warning: Error installing {package}: {e}")
                print("Continuing with installation...")

        print("✓ Successfully installed Python packages")
        print("\nNote: If you encounter any issues with the dependencies, you can try:")
        print("  pip install -r requirements.txt")
    except Exception as e:
        print(f"Error during package installation: {e}")
        print("\nAlternative installation method:")
        print("  pip install -r requirements.txt")


def check_bgpq4():
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


def main():
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

    # Install packages based on version
    install_python_packages(lite=args.lite)

    # Check for bgpq4 if not using the lite version
    if not args.lite:
        check_bgpq4()

    # Print completion message based on version
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
