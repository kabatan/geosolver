"""Linux/WSL exec bootstrap: pin before importing the solver; cap single files/AS."""
import os
import resource
import sys

if __name__ == '__main__':
    cpu, address_mib = map(int, sys.argv[1:3])
    os.sched_setaffinity(0, {cpu})
    resource.setrlimit(resource.RLIMIT_FSIZE, (2_900_000, 2_900_000))
    resource.setrlimit(resource.RLIMIT_AS, (address_mib*1024**2, address_mib*1024**2))
    os.execv(sys.argv[3], sys.argv[3:])
