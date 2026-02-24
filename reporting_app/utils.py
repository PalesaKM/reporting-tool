from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def send_report_update_email(report, status_change):
    """
    Sends an email notification about a report update to all associated managers
    and the supervisor who created the report.
    """
    supervisor = report.supervisor
    recipient_list = []

    supervisor_email = supervisor.user.email if supervisor.user and supervisor.user.email else None
    if supervisor_email:
        recipient_list.append(supervisor_email)
        print(f"Adding Supervisor: {supervisor_email}")

    try:
        managers = supervisor.managers.all()
        manager_emails = [
            manager.user.email
            for manager in managers
            if manager.user and manager.user.email
        ]
        if manager_emails:
            recipient_list.extend(manager_emails)
            print(f"Adding Managers: {', '.join(manager_emails)}")
    except AttributeError:
        print(
            f"EMAIL ERROR: Could not find managers for Supervisor {supervisor}. "
            "Check the related_name on your Manager model."
        )
        return

    if not recipient_list:
        print(
            f"EMAIL SKIPPED: No recipients (supervisor or managers) with valid "
            f"emails found for Report #{report.pk}."
        )
        return

    report_type = f"Report #{report.pk} (Week {report.week_number})"
    subject = f"ReportFlow Update: {report_type} was {status_change}"

    base_url = getattr(settings, "SITE_BASE_URL", "http://10.11.4.83:8000").rstrip("/")
    report_path = reverse("report_detail", kwargs={"pk": report.pk})
    report_url = f"{base_url}{report_path}"

    body = (
        f"Hello,\n\n"
        f"A report from Supervisor '{supervisor.user.get_full_name() or supervisor.user.username}' has been updated.\n\n"
        f" - Report: {report_type}\n"
        f" - Action: {status_change.title()}\n"
        f" - Current Status: {report.get_status_display()}\n\n"
        f"You can view the report here:\n"
        f"{report_url}\n\n"
        f"Thank you,\n"
        f"ReportFlow Automated System"
    )

    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
        )
        print(f"Email sent successfully for Report #{report.pk} to: {', '.join(recipient_list)}")
    except Exception as exc:
        print(f"EMAIL ERROR: Failed to send email for Report {report.pk}. Error: {exc}")
