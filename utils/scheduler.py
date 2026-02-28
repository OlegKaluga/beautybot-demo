# utils/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import pytz
from config.settings import get_settings

settings = get_settings()
tz = pytz.timezone(settings["TIMEZONE"])


class ReminderScheduler:
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone=tz)
        self.jobs = {}

    async def start(self):
        self.scheduler.start()
        # Восстановление задач после перезапуска
        pending = await self.db.get_pending_reminders()
        for bid, uid, name, svc, date, time, remind_at in pending:
            dt = datetime.fromisoformat(remind_at)
            if dt > datetime.now(tz):
                self._schedule(bid, uid, name, svc, date, time, dt)

    def _schedule(self, bid, uid, name, svc, date, time, remind_at):
        async def send():
            try:
                text = settings["REMINDER_TEXT"].format(service=svc or "процедуру", time=time)
                await self.bot.send_message(uid, f"💅 <b>Напоминание</b>\n\n{text}", parse_mode="HTML")
                await self.db.mark_reminder_sent(bid)
            except Exception as e:
                print(f"Reminder error: {e}")

        job = self.scheduler.add_job(send, trigger=DateTrigger(run_date=remind_at),
                                    id=f"rem_{bid}", replace_existing=True)
        self.jobs[bid] = job.id

    async def add(self, bid, uid, name, svc, date, time, appt_dt):
        remind_at = appt_dt - timedelta(hours=24)
        if remind_at <= datetime.now(tz):
            return
        await self.db.add_reminder_task(bid, remind_at.isoformat())
        self._schedule(bid, uid, name, svc, date, time, remind_at)

    def cancel(self, bid):
        if bid in self.jobs:
            try:
                self.scheduler.remove_job(self.jobs[bid])
            except:
                pass
            del self.jobs[bid]

    def shutdown(self):
        self.scheduler.shutdown()
