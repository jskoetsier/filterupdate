#!/usr/bin/env python3
"""
Setup script for filterupdate tool.
This script installs the required Python packages and checks for the bgpq3 command-line tool.
"""

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


def install_python_packages():
    """Install required Python packages."""
    print("\nInstalling required Python packages...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
        )
        subprocess.check_call([sys.executable, "-m", "pip", "install", "junos-eznc"])
        print("✓ Successfully installed Python packages")
    except subprocess.CalledProcessError as e:
        print(f"Error installing packages: {e}")
        sys.exit(1)


def check_bgpq3():
    """Check if bgpq3 is installed and provide installation instructions if not."""
    print("\nChecking for bgpq3...")
    try:
        subprocess.check_call(
            ["which", "bgpq3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✓ bgpq3 is installed")
    except subprocess.CalledProcessError:
        print("✗ bgpq3 is not installed")
        system = platform.system()

        print("\nInstallation instructions for bgpq3:")

        if system == "Darwin":  # macOS
            print(
                """
On macOS:
    Using Homebrew: brew install bgpq3
    Using MacPorts: sudo port install bgpq3
            """
            )
        elif system == "Linux":
            print(
                """
On Linux:
    Debian/Ubuntu: sudo apt-get install bgpq3
    CentOS/RHEL:
        1. Install EPEL repository if not already installed:
           sudo yum install epel-release
        2. Install bgpq3:
           sudo yum install bgpq3

    Alternatively, install from source:
    git clone https://github.com/snar/bgpq3.git
    cd bgpq3
    ./configure
    make
    sudo make install
            """
            )
        else:
            print(
                """
Please install bgpq3 from source:
    git clone https://github.com/snar/bgpq3.git
    cd bgpq3
    ./configure
    make
    sudo make install
            """
            )


def main():
    """Main function to run the setup."""
    print("Setting up filterupdate tool...\n")

    check_python_version()
    install_python_packages()
    check_bgpq3()

    print("\nSetup complete! You can now use the filterupdate.py script.")
    print("Run 'python3 filterupdate.py -h' for usage instructions.")


if __name__ == "__main__":
    main()
