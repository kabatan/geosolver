"""Private JSON-lines server; never runs numerical search concurrently."""

import json
import os
import signal
import sys
import threading


def main():
    parent = int(os.environ["GEOSOLVER_SYMBOLIC_PARENT"])
    stopped = threading.Event()

    def watch_parent():
        import psutil

        try:
            owner = psutil.Process(parent)
            created = owner.create_time()
        except psutil.Error:
            os._exit(1)
        while not stopped.wait(0.1):
            try:
                alive = (
                    owner.is_running()
                    and owner.create_time() == created
                    and owner.status() != psutil.STATUS_ZOMBIE
                )
            except psutil.Error:
                alive = False
            if not alive:
                if os.name == "posix":
                    os.killpg(os.getpid(), signal.SIGKILL)
                os._exit(1)

    threading.Thread(target=watch_parent, daemon=True).start()
    from geosolver.runtime.symbolic_operations import dispatch

    try:
        for line in sys.stdin:
            try:
                message = json.loads(line)
                from geosolver.runtime.deadline import check_deadline, uses_deadline

                @uses_deadline
                def execute(*, deadline_monotonic, message=message):
                    check_deadline()
                    return dispatch(message["operation"], message["payload"])

                result = {"result": execute(deadline_monotonic=message.get("deadline"))}
            except Exception as exc:
                result = {"error": f"{type(exc).__name__}: {exc}", "error_type": type(exc).__name__}
            print(json.dumps(result), flush=True)
    finally:
        stopped.set()


if __name__ == "__main__":
    main()
