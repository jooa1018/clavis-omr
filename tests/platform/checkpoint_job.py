"""A synthetic job held at its first checkpoint until the runner signals stop."""

import time

from training.jobs.context import Context


def main() -> None:
    context = Context()
    state = context.load()
    if state is None:
        context.save({"step": 1, "total": 0})
        # File protocol is the synchronization event. Wall limits only bound test failure.
        while not context.stopping():
            time.sleep(0.01)
        return
    while state["step"] < 20:
        state["total"] += state["step"]
        state["step"] += 1
        context.save(state)


if __name__ == "__main__":
    main()
