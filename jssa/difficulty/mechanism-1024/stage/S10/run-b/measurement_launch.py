"""Linux/WSL exec bootstrap: pin before importing the solver; cap solver files at 1GiB and address space."""
import os
import resource
import sys

if __name__ == '__main__':
    cpu, address_mib = map(int, sys.argv[1:3])
    os.sched_setaffinity(0, {cpu})
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_AS, (address_mib*1024**2, address_mib*1024**2))
    os.execv(sys.argv[3], sys.argv[3:])
