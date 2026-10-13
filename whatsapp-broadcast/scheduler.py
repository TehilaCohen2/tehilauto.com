"""תזמון עם APScheduler (תהליך שרץ ברצף, למשל על שרת / Raspberry Pi).
בענן אפשר להשתמש ב-.github/workflows/whatsapp-broadcast.yml במקום."""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import tasks
from store import Store


def job(fn):
    def run():
        fn(Store())
    return run


def main():
    s = BlockingScheduler(timezone=config.TZ)
    # ראשון 09:00 | רביעי 09:00 | מוצאי שבת (שבת) 20:00 | בדיקת תשובות כל 3 שעות
    s.add_job(job(tasks.task1_prepare), CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=config.TZ))
    s.add_job(job(tasks.task2_post), CronTrigger(day_of_week="wed", hour=9, minute=0, timezone=config.TZ))
    s.add_job(job(tasks.task3_propose), CronTrigger(day_of_week="sat", hour=20, minute=0, timezone=config.TZ))
    s.add_job(job(tasks.check_approvals), CronTrigger(hour="*/3", minute=15, timezone=config.TZ))
    s.start()


if __name__ == "__main__":
    main()
