from django.urls import path
from . import views
from .api_views import last_30_days_reports

urlpatterns = [
    path("home/", views.login_redirect, name="login_redirect"),
    path("", views.supervisor_home, name="supervisor_home"),
    path("manager_dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("submit_report/", views.submit_report, name="submit_report"),
    path('submit_report/<int:report_pk>/', views.submit_report, name='submit_report'), 
    path("request_extension/", views.request_extension, name="request_extension"),
    path("manager_extension_requests/", views.manager_extension_requests, name="manager_extension_requests"),
    path("report_success/<int:report_pk>/", views.report_success, name="report_success"),
    path("edit_report/<int:report_pk>/", views.edit_report, name="edit_report"),
    path("report/<int:pk>/", views.report_detail, name="report_detail"),
    path("my_reports/", views.list_reports, name="list_reports"),
    path("delete_report/<int:pk>/", views.delete_report, name="delete_report"),
    path('report/download/<int:pk>/', views.download_single_report, name='download_single_report'),
    path("submit_daily_report/", views.submit_daily_report, name="submit_daily_report"),
    path("submit_daily_report/<int:report_pk>/", views.submit_daily_report, name="submit_daily_report"),
    path("admin_dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin_daily_reports/", views.admin_daily_reports, name="admin_daily_reports"),
    path("manager_daily_reports/", views.manager_daily_reports, name="manager_daily_reports"),
    path("daily_report/<int:pk>/", views.daily_report_detail, name="daily_report_detail"),
    path("supervisor_daily_reports/", views.supervisor_daily_reports, name="supervisor_daily_reports"),
    path("supervisor_daily_report/<int:pk>/", views.supervisor_daily_report_detail, name="supervisor_daily_report_detail"),
    path('api/reports/last-30-days/', last_30_days_reports, name='last_30_days_reports'),
]
