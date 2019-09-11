#!/usr/bin/env python
import sys
import argparse
import os
import subprocess
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.exception import ConnectError
from jnpr.junos.exception import LockError
from jnpr.junos.exception import UnlockError
from jnpr.junos.exception import ConfigLoadError
from jnpr.junos.exception import CommitError

# (c) 2019 - Sebastiaan Koetsier - licensed under MIT license, see license.txt

def startwork(host_device,asset,prefixlist,ipv6):
    outfile = open("temp.conf", "w")
    config = "temp.conf"
    os.system('clear')
    print ("~ Starting bgpq3 ...")
    if ipv6 == True:
        subprocess.call(["bgpq3", "-J", asset,"-l",prefixlist,"-6","-h","rr.ntt.net"], stdout=outfile)
    else:
        subprocess.call(["bgpq3", "-J", asset,"-l",prefixlist,"-h","rr.ntt.net"], stdout=outfile)
    outfile.close()

    with open(config, 'r') as fin:
        print ("======[ Writing prefix filter ]======")
        print fin.read()
        print ("======[ Done writing filter ]======")

    print ("======[ Action log ]======")

    try:
        dev = Device(host=host_device)
        dev.open()
    except ConnectError as err:
        print ("-- Unable to connect to: {0}".format(err))
        return

    dev.bind(cu=Config)

    print ("++ Locking configuration")
    try:
        dev.cu.lock()
    except LockError as err:
        print ("-- Unable to lock configuration {0}".format(err))
        return

    print ("++ Loading prefixlist configuration")
    try:
        dev.cu.load(path=config,replace=True)
    except (ConfigLoadError, Exception) as err:
        print ("-- Unable to load configuration changes: {0}".format(err))
        print ("++ Unlocking configuration")
        try:
            dev.cu.unlock()
        except UnlockError:
            print ("-- Unable to unlock configuration: {0}".format(err))
        dev.close()
        return

    print ("++ Committing the configuration")
    try:
        dev.cu.commit(comment='Prefix filter update')
    except CommitError as err:
        print ("-- Unable to commit configuration: {0}".format(err))
        print ("++ Unlocking the configuration")
        try:
            dev.cu.unlock()
        except UnlockError as err:
            print ("-- Unable to unlock configuration: {0}".format(err))
        dev.close()
        return

    print ("++ Unlocking the configuration")
    try:
        dev.cu.unlock()
    except UnlockError as err:
        print ("-- Unable to unlock configuration: {0}".format(err))

    dev.close()
    os.remove(config)
    exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', action='store', type=str, help="Which device to use", dest="host_device", required=True)
    parser.add_argument('-a', action='store', type=str, help="AS-SET to create prefixlist", dest="asset", required=True)
    parser.add_argument('-l', action='store', type=str, help="prefix-list name", dest="prefixlist", required=True)
    parser.add_argument('-6', action='store_true', default=False, help="Use IPv6", dest="ipv6", required=False)
    args = parser.parse_args()

    host_device = '%s' % (args.host_device)
    asset = '%s' % (args.asset)
    prefixlist = '%s' % (args.prefixlist)
    ipv6 = (args.ipv6)

    startwork(host_device,asset,prefixlist,ipv6)
    sys.exit(2)

if __name__ == "__main__":
    main()
