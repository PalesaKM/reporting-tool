# utils.py
import http
from django.core.mail import send_mail
from django.conf import settings
# from django.urls import reverse 
from .models import ReportContent # Assuming ReportContent holds the report details

def send_report_update_email(report, status_change):
    """
    Sends an email notification about a report update to all associated managers 
    AND the supervisor who created the report.
    """
    
    # 1. Get the supervisor and initialize the recipient list
    supervisor = report.supervisor
    recipient_list = []
    
    # --- A. ADD SUPERVISOR'S EMAIL ---
    supervisor_email = supervisor.user.email if supervisor.user and supervisor.user.email else None
    if supervisor_email:
        recipient_list.append(supervisor_email)
        print(f"Adding Supervisor: {supervisor_email}")


    # --- B. ADD ALL MANAGERS' EMAILS ---
    try:
        # This assumes the related_name on the Manager model pointing back to Supervisor is 'managers'.
        managers = supervisor.manager_set.all()
        
        manager_emails = [
            manager.user.email 
            for manager in managers 
            if manager.user and manager.user.email
        ]
        
        if manager_emails:
             recipient_list.extend(manager_emails)
             print(f"Adding Managers: {', '.join(manager_emails)}")
             
    except AttributeError:
        # Catches the error if 'managers' related_name is incorrect or missing.
        print(f"EMAIL ERROR: Could not find managers for Supervisor {supervisor}. Check the 'related_name' on your Manager model.")
        return

    
    # 2. Final Check for Recipients
    if not recipient_list:
        print(f"EMAIL SKIPPED: No recipients (supervisor or managers) with valid emails found for Report #{report.pk}.")
        return

    # 3. Define Subject and Body (Keep generic since it goes to multiple roles)
    report_type = f"Report #{report.pk} (Week {report.week_number})"
    subject = f"ReportFlow Update: {report_type} was {status_change}"
    
    # A cleaner placeholder for the URL in a LAN environment:
    lan_ip = "YOUR_LAN_IP" # Replace with your actual LAN IP (e.g., 10.11.4.83)
    report_url = f"http://10.11.4.83:8000/reports/{report.pk}/"

    body = (
        f"Hello,\n\n"
        f"A report from Supervisor '{supervisor.user.get_full_name() or supervisor.user.username}' has been updated.\n\n"
        f"  - Report: {report_type}\n"
        f"  - Action: {status_change.title()}\n"
        f"  - Current Status: {report.get_status_display()}\n\n"
        f"You can view the report here:\n"
        f"{report_url}\n\n"
        f"Thank you,\n"
        f"ReportFlow Automated System"
    )
    
    # 4. Send Email
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            # Send to the combined list of supervisor and manager emails
            recipient_list,
            fail_silently=False, 
        )
        print(f"Email sent successfully for Report #{report.pk} to: {', '.join(recipient_list)}")
    except Exception as e:
        print(f"EMAIL ERROR: Failed to send email for Report {report.pk}. Error: {e}")