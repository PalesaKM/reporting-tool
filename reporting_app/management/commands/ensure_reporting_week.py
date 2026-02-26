from datetime import date

from django.core.management.base import BaseCommand, CommandError

from reporting_app.helpers import ensure_reporting_week, seed_weekly_deadlines_from_previous
from reporting_app.models import ReportingWeek


class Command(BaseCommand):
    help = "Ensure ReportingWeek exists and seed supervisor deadlines from previous week pattern."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            help="Optional ISO date (YYYY-MM-DD). If omitted, uses today.",
        )

    def handle(self, *args, **options):
        target_date_arg = options.get("target_date")
        if target_date_arg:
            try:
                target_date = date.fromisoformat(target_date_arg)
            except ValueError as exc:
                raise CommandError("--date must be in YYYY-MM-DD format.") from exc
        else:
            target_date = date.today()

        iso = target_date.isocalendar()
        week_number = iso.week
        year = iso.year

        existed = ReportingWeek.objects.filter(
            week_number=week_number,
            year=year,
        ).exists()
        reporting_week = ensure_reporting_week(week_number, year)
        created = not existed
        seeded_count = seed_weekly_deadlines_from_previous(reporting_week)

        status = "CREATED" if created else "EXISTS"
        self.stdout.write(
            self.style.SUCCESS(
                f"{status}: week={reporting_week.week_number}, year={reporting_week.year}, "
                f"start={reporting_week.start_date}, end={reporting_week.end_date}, "
                f"seeded_deadlines={seeded_count}"
            )
        )
