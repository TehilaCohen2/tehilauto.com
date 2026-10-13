"""נקודת כניסה: python broadcast.py <פקודה> [--force]

task1 | task2 | task3 | approvals | seed | run-due
run-due: מריץ את מה שמגיע לפי שעון ישראל עכשיו (לשימוש ב-cron / GitHub Actions)."""
import argparse
import sys

import config
import tasks
from store import Store


def run_due(store):
    n = config.now()
    wd, h = n.weekday(), n.hour  # שני=0 ... ראשון=6
    if wd == 6 and h == 9:
        tasks.task1_prompt(store)
    if wd == 2 and h == 9:
        tasks.task2_post(store)
    if wd == 5 and h == 20:
        tasks.task3_propose(store)
    tasks.check_approvals(store)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["task1", "task2", "task3", "approvals", "seed", "run-due"])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    store = Store()
    {
        "task1": lambda: tasks.task1_prompt(store, a.force),
        "task2": lambda: tasks.task2_post(store, a.force),
        "task3": lambda: tasks.task3_propose(store, a.force),
        "approvals": lambda: tasks.check_approvals(store),
        "seed": lambda: tasks.seed(store),
        "run-due": lambda: run_due(store),
    }[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())
