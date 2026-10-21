"""Windows startup barrier, before executing a solve-owned command."""

import subprocess
import sys


def main():
    from geosolver.platform.windows_job import wait_for_owner

    wait_for_owner(sys.argv[1])
    return subprocess.call(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
