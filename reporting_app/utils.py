import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def _append_email_if_present(recipient_list, value):
    if value and value not in recipient_list:
        recipient_list.append(value)


def _supervisor_email(supervisor):
    if supervisor is None:
        return None
    if getattr(supervisor, "user", None) and supervisor.user.email:
        return supervisor.user.email
    return getattr(supervisor, "email", None)


def _manager_emails_for_supervisor(supervisor):
    if supervisor is None:
        return []
    manager_emails = []
    try:
        managers = supervisor.managers.all()
    except AttributeError:
        return manager_emails

    for manager in managers:
        email = None
        if getattr(manager, "user", None) and manager.user.email:
            email = manager.user.email
        elif getattr(manager, "email", None):
            email = manager.email
        _append_email_if_present(manager_emails, email)
    return manager_emails


def _build_absolute_url(view_name, kwargs):
    base_url = getattr(settings, "SITE_BASE_URL", "http://10.11.4.83:8000").rstrip("/")
    return f"{base_url}{reverse(view_name, kwargs=kwargs)}"


def _send_notification_email(subject, body, recipients):
    if not recipients:
        return
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Email send failed for subject '%s'.", subject)


def send_report_update_email(report, status_change):
    supervisor = report.supervisor
    recipient_list = []
    _append_email_if_present(recipient_list, _supervisor_email(supervisor))
    for email in _manager_emails_for_supervisor(supervisor):
        _append_email_if_present(recipient_list, email)

    if not recipient_list:
        logger.warning("No recipients found for weekly report #%s notification.", report.pk)
        return

    report_type = f"Report #{report.pk} (Week {report.week_number})"
    subject = f"ReportFlow Update: {report_type} was {status_change}"
    report_url = _build_absolute_url("report_detail", {"pk": report.pk})

    supervisor_name = (
        supervisor.user.get_full_name() or supervisor.user.username
        if getattr(supervisor, "user", None)
        else str(supervisor)
    )
    body = (
        "Hello,\n\n"
        f"A weekly report from Supervisor '{supervisor_name}' has been updated.\n\n"
        f" - Report: {report_type}\n"
        f" - Action: {status_change}\n"
        f" - Current Status: {report.get_status_display()}\n\n"
        "You can view the report here:\n"
        f"{report_url}\n\n"
        "Thank you,\n"
        "ReportFlow Automated System"
    )
    _send_notification_email(subject, body, recipient_list)


def send_extension_request_email(extension_request, event_label):
    supervisor = extension_request.supervisor
    recipient_list = []
    _append_email_if_present(recipient_list, _supervisor_email(supervisor))
    for email in _manager_emails_for_supervisor(supervisor):
        _append_email_if_present(recipient_list, email)

    if not recipient_list:
        logger.warning("No recipients found for extension request #%s notification.", extension_request.pk)
        return

    subject = f"ReportFlow Extension Update: Request #{extension_request.pk} {event_label}"
    extension_url = _build_absolute_url("manager_extension_requests", {})
    supervisor_name = (
        supervisor.user.get_full_name() or supervisor.user.username
        if getattr(supervisor, "user", None)
        else str(supervisor)
    )
    reason = extension_request.reason or "No reason provided."
    manager_comment = extension_request.manager_comment or "No manager comment."
    body = (
        "Hello,\n\n"
        "An extension request has been updated.\n\n"
        f" - Request: #{extension_request.pk}\n"
        f" - Supervisor: {supervisor_name}\n"
        f" - Status: {extension_request.status}\n"
        f" - Requested Until: {extension_request.requested_until}\n"
        f" - Reason: {reason}\n"
        f" - Manager Comment: {manager_comment}\n\n"
        "You can review extension requests here:\n"
        f"{extension_url}\n\n"
        "Thank you,\n"
        "ReportFlow Automated System"
    )
    _send_notification_email(subject, body, recipient_list)


def send_daily_report_update_email(daily_report, status_change):
    supervisor = daily_report.supervisor
    recipient_list = []
    _append_email_if_present(recipient_list, _supervisor_email(supervisor))
    for email in _manager_emails_for_supervisor(supervisor):
        _append_email_if_present(recipient_list, email)

    if not recipient_list:
        logger.warning("No recipients found for daily report #%s notification.", daily_report.pk)
        return

    subject = f"ReportFlow Daily Update: Report #{daily_report.pk} was {status_change}"
    report_url = _build_absolute_url("daily_report_detail", {"pk": daily_report.pk})
    supervisor_name = (
        supervisor.user.get_full_name() or supervisor.user.username
        if supervisor and getattr(supervisor, "user", None)
        else str(supervisor or "Unassigned")
    )
    body = (
        "Hello,\n\n"
        f"A daily report for Supervisor '{supervisor_name}' has been updated.\n\n"
        f" - Report: Daily #{daily_report.pk}\n"
        f" - Action: {status_change}\n"
        f" - Current Status: {daily_report.get_status_display()}\n\n"
        "You can view the daily report here:\n"
        f"{report_url}\n\n"
        "Thank you,\n"
        "ReportFlow Automated System"
    )
    _send_notification_email(subject, body, recipient_list)
