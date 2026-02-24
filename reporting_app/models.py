from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


    
class Department(models.Model):
    name= models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Admin(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="admins")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class Supervisor(models.Model):
    first_name= models.CharField(max_length=50)
    last_name= models.CharField(max_length=50)
    phone_number= models.CharField(max_length=20)
    email= models.EmailField(unique=True)
    assigned_projects = models.ManyToManyField('Project', related_name='assigned_supervisors', blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="supervisor_profile", null=True, blank=True)
    department= models.ForeignKey(Department, on_delete=models.CASCADE, related_name="supervisors")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Manager(models.Model):
    first_name= models.CharField(max_length=50)
    last_name= models.CharField(max_length=50)
    phone_number= models.CharField(max_length=20)
    email= models.EmailField(unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="manager_profile", null=True, blank=True)
    supervisor= models.ManyToManyField(Supervisor, blank= True, related_name="managers")
    

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class WeeklyReport(models.Model):
    
    STATUS_CHOICES=[
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Reviewed", "Reviewed"),
        ("Rejected", "Rejected"),
        ('Rework', 'Rework'),
        ('Approved', 'Approved'),
        ('Waived', 'Waived')
    ]
    submission_timestamp= models.DateTimeField(auto_now_add=True)
    created_at= models.DateTimeField(default= timezone.now)
    status_changed_at = models.DateTimeField(default=timezone.now)
    status= models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    is_locked= models.BooleanField(default=False)
    week_number = models.PositiveIntegerField(null=True, blank=True)
    supervisor= models.ForeignKey(Supervisor, on_delete=models.CASCADE,related_name="weekly_reports")
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Report {self.id} (Week {self.week_number or 'N/A'}) - {self.supervisor} - {self.status}"
    def save(self, *args, **kwargs):
        if self.pk:
            previous = WeeklyReport.objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] != self.status:
                self.status_changed_at = timezone.now()
        else:
            if not self.status_changed_at:
                self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)

    def can_edit(self):
        if self.status == "Draft":
            return True
        if self.status in ["Submitted", "Rework"]:
            if not self.status_changed_at:
                return False
            return timezone.now() <= self.status_changed_at + timedelta(hours=1)
        return False

    def edit_window_remaining_seconds(self):
        if self.status in ["Submitted", "Rework"] and self.status_changed_at:
            remaining = (self.status_changed_at + timedelta(hours=1)) - timezone.now()
            return max(0, int(remaining.total_seconds()))
        return 0
    class Meta:
        permissions = [
            ("view_all_weekly_reports", "Can view all weekly reports"),
            ("review_weekly_reports", "Can review weekly reports"),
        ]

class ReportContent(models.Model):
    CATEGORY_CONTENT=[
        ("Green", "Green"),
        ("Amber", "Amber"),
        ("Risk", "Risk")
    ]
    category= models.CharField(max_length=10, choices= CATEGORY_CONTENT)
    entry= models.TextField(blank=True, null=True)
    project = models.ForeignKey('Project', on_delete=models.SET_NULL, null=True, blank=True, related_name="report_contents")
    project_name = models.CharField(max_length=200, blank=True)
    report= models.ForeignKey(WeeklyReport, on_delete= models.CASCADE, related_name="contents")
    manager_comment= models.TextField(blank=True, null= True)
    def __str__(self):
        return f"{self.category} - Report {self.report.id}"

class ReportingWeek(models.Model):
    week_number = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"Week {self.week_number} - {self.year}"
    
class SubmissionDeadline(models.Model):
    supervisor = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="deadlines")
    reporting_week = models.ForeignKey(ReportingWeek, on_delete=models.CASCADE, related_name="deadlines")
    due_datetime = models.DateTimeField()
    extended_datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.supervisor} - Week {self.reporting_week.week_number}"

class ExtensionRequest(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]
    supervisor = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="extension_requests")
    report = models.ForeignKey(WeeklyReport, on_delete=models.SET_NULL, null=True, blank=True, related_name="extension_requests")
    requested_until = models.DateTimeField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    manager_comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Extension {self.id} - {self.supervisor} - {self.status}"
    
class Comment(models.Model):
    comment_text= models.TextField(default="Enter text")
    time_stamp= models.DateTimeField(auto_now_add=True)
    report= models.ForeignKey(WeeklyReport, on_delete= models.CASCADE, related_name= "comments")
    manager= models.ForeignKey(Manager, on_delete= models.CASCADE, related_name= "comments")

    def __str__(self):
        return f"Comment by {self.manager} on Report {self.report.id}"
    
class Project(models.Model):
    name= models.CharField(max_length=100)
    manager= models.ForeignKey(Manager, on_delete=models.CASCADE, related_name="project")

    def __str__(self):
        return self.name

class DailyReport(models.Model):
    STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Reviewed", "Reviewed"),
        ("Rejected", "Rejected"),
        ("Rework", "Rework"),
        ("Approved", "Approved"),
        ("Waived", "Waived"),
    ]

    admin = models.ForeignKey(
        Admin, on_delete=models.CASCADE, related_name="daily_reports", null=True, blank=True
    )
    supervisor = models.ForeignKey(
        Supervisor, on_delete=models.SET_NULL, null=True, blank=True, related_name="daily_reports"
    )
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="daily_reports"
    )
    project_name = models.CharField(max_length=200, blank=True)

    submission_timestamp = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_locked = models.BooleanField(default=False)
    status_changed_at = models.DateTimeField(default=timezone.now)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    class Meta:
        permissions = [
            ("view_all_daily_reports", "Can view all daily reports"),
        ]
    def __str__(self):
        return f"Daily Report {self.id} - {self.admin.user.username} - {self.status}"
    def save(self, *args, **kwargs):
        if self.pk:
            previous = DailyReport.objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] != self.status:
                self.status_changed_at = timezone.now()
        else:
            if not self.status_changed_at:
                self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)

    def can_edit(self):
        if self.status == "Draft":
            return True
        if self.status in ["Submitted", "Rework"]:
            if not self.status_changed_at:
                return False
            return timezone.now() <= self.status_changed_at + timedelta(hours=1)
        return False

    def edit_window_remaining_seconds(self):
        if self.status in ["Submitted", "Rework"] and self.status_changed_at:
            remaining = (self.status_changed_at + timedelta(hours=1)) - timezone.now()
            return max(0, int(remaining.total_seconds()))
        return 0

class DailyReportContent(models.Model):
    CATEGORY_CHOICES = [
        ("Green", "Green"),
        ("Amber", "Amber"),
        ("Risk", "Risk")
    ]

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    entry = models.TextField(blank=True, null=True)

    report = models.ForeignKey(
        DailyReport, on_delete=models.CASCADE, related_name="contents"
    )
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True
    )
    project_name = models.CharField(max_length=200, blank=True)

    supervisor_comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.category} - DailyReport {self.report.id}"

class DailyReportComment(models.Model):
    comment_text = models.TextField(default="Enter text")
    time_stamp = models.DateTimeField(auto_now_add=True)
    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name="comments")
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE, related_name="daily_report_comments")

    def __str__(self):
        return f"Daily Comment by {self.manager} on Report {self.report.id}"

class DailyReportSupervisorComment(models.Model):
    comment_text = models.TextField(default="Enter text")
    time_stamp = models.DateTimeField(auto_now_add=True)
    report = models.ForeignKey(DailyReport, on_delete=models.CASCADE, related_name="supervisor_comments")
    supervisor = models.ForeignKey(Supervisor, on_delete=models.CASCADE, related_name="daily_report_comments")

    def __str__(self):
        return f"Daily Comment by {self.supervisor} on Report {self.report.id}"
