from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    Department,
    Supervisor,
    Manager,
    WeeklyReport,
    ReportContent,
    Comment,
    SubmissionDeadline,
    Project,
    Admin,
    DailyReport,
    DailyReportContent,
    DailyReportComment,
    DailyReportSupervisorComment,
    ExtensionRequest,
)


class ReportContentInline(admin.TabularInline):
    model = ReportContent
    fields = ('project_name', 'category', 'entry', 'manager_comment') 
    extra = 0
    readonly_fields= ('project_name', 'category', 'entry')

class CommentInline(admin.TabularInline):
    model = Comment
    fields = ('manager', 'comment_text')
    readonly_fields = ('manager',) 
    extra = 0 

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        try:
            request.user.manager_profile
            return True
        except ObjectDoesNotExist:
            return False
        
    def has_change_permission(self, request, obj=None):
        return self.has_add_permission(request,obj)
    def has_delete_permission(self, request, obj=None):
        return self.has_add_permission(request,obj)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name== "manager" and not request.user.is_superuser:
            try:
                kwargs["initial"] = Manager.objects.get(user=request.user)
                kwargs["queryset"]= Manager.objects.filter(user=request.user)
            except ObjectDoesNotExist:
                pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class DailyReportContentInline(admin.TabularInline):
    model = DailyReportContent
    fields = ("project_name", "category", "entry", "supervisor_comment")
    extra = 0
    readonly_fields = ("project_name", "category", "entry")


class DailyReportManagerCommentInline(admin.TabularInline):
    model = DailyReportComment
    fields = ("manager", "comment_text", "time_stamp")
    readonly_fields = ("manager", "time_stamp")
    extra = 0


class DailyReportSupervisorCommentInline(admin.TabularInline):
    model = DailyReportSupervisorComment
    fields = ("supervisor", "comment_text", "time_stamp")
    readonly_fields = ("supervisor", "time_stamp")
    extra = 0

@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    
    list_display = ('id', 'supervisor', 'status', 'submission_timestamp', 'comment_count')
    list_filter = ('status', 'submission_timestamp')
    search_fields = ('supervisor__first_name', 'supervisor__last_name', 'id')
    list_per_page = 25
    inlines = [ReportContentInline, CommentInline]
    readonly_fields = ('submission_timestamp', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('supervisor', 'week_number', 'status')
        }),
        ('Timestamps',{
            'fields': ('created_at', 'submission_timestamp'),
            'classes': ('collapse',)
        })
    )
    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        fields.extend(['created_at', 'submission_timestamp'])
        
        if obj and obj.status == 'Submitted' and not request.user.is_superuser:
            fields.extend(['supervisor', 'week_number', 'status'])
            
        return fields
    
    def comment_count(self, obj):
        return obj.comments.count()
    comment_count.short_description = "Comments"

@admin.register(ReportContent)
class ReportContentAdmin(admin.ModelAdmin):
    
    list_display = ('report', 'project_name', 'category', 'entry')
    list_filter = ('category',)
    search_fields = ('entry', 'report__id')
    list_per_page = 25


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'department', 'admins_in_department')
    list_filter = ('department',)
    search_fields = ('user__username', 'first_name', 'last_name')
    autocomplete_fields = ['department', 'user']

    def user_first_name(self, obj):
        return obj.user.first_name
    def user_last_name(self, obj):
        return obj.user.last_name
    user_first_name.short_description = "First Name"
    user_last_name.short_description = "Last Name"
    def admins_in_department(self, obj):
        admins = Admin.objects.filter(department=obj.department).select_related("user")
        names = [a.user.get_full_name() or a.user.username for a in admins]
        return ", ".join(names) if names else "—"
    admins_in_department.short_description = "Admins"
    


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'get_supervised_count')
    filter_horizontal = ('supervisor',)
    search_fields = ('user__username', 'first_name', 'last_name')
    def get_supervised_count(self, obj):
        """Custom display method to count the number of supervisors managed."""
        return obj.supervisor.count()
    get_supervised_count.short_description = 'Supervisors Managed'

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(SubmissionDeadline)
class SubmissionDeadlineAdmin(admin.ModelAdmin):
    
    list_display = ('supervisor', 'due_datetime', 'extended_datetime') 
    list_filter = ('supervisor__department',)
    date_hierarchy = 'due_datetime' 


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager')
    search_fields = ('name', 'manager__first_name', 'manager__last_name')
    autocomplete_fields = ['manager'] 


@admin.register(Admin)
class AdminAdmin(admin.ModelAdmin):
    list_display = ("user", "first_name", "last_name", "email", "department")
    search_fields = ("user__username", "first_name", "last_name", "email")
    autocomplete_fields = ["user", "department"]


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ("id", "admin", "supervisor", "project_name_display", "status", "submission_timestamp")
    list_filter = ("status", "submission_timestamp", "supervisor")
    search_fields = ("admin__first_name", "admin__last_name", "supervisor__first_name", "supervisor__last_name", "id")
    readonly_fields = ("submission_timestamp", "created_at")
    inlines = [DailyReportContentInline, DailyReportSupervisorCommentInline, DailyReportManagerCommentInline]
    def project_name_display(self, obj):
        return obj.project_name or (obj.project.name if obj.project else "—")
    project_name_display.short_description = "Project"


@admin.register(DailyReportContent)
class DailyReportContentAdmin(admin.ModelAdmin):
    list_display = ("report", "project_name", "category", "entry")
    list_filter = ("category",)
    search_fields = ("entry", "report__id")


@admin.register(DailyReportComment)
class DailyReportCommentAdmin(admin.ModelAdmin):
    list_display = ("report", "manager", "time_stamp")
    search_fields = ("report__id", "manager__first_name", "manager__last_name")


@admin.register(DailyReportSupervisorComment)
class DailyReportSupervisorCommentAdmin(admin.ModelAdmin):
    list_display = ("report", "supervisor", "time_stamp")
    search_fields = ("report__id", "supervisor__first_name", "supervisor__last_name")


@admin.register(ExtensionRequest)
class ExtensionRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "supervisor", "requested_until", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("supervisor__first_name", "supervisor__last_name", "id")
