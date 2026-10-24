"""S8 driver proposal: implemented entry point is preflight only.

Main execution is intentionally absent in this preparation-only delivery.
"""
import sys
from verify_preparation import main

if __name__ == '__main__':
    if sys.argv[1:2] != ['verify-plan']:
        raise SystemExit('Preparation only: supported command is verify-plan; main measurement is not implemented/enabled.')
    del sys.argv[1]
    main()
