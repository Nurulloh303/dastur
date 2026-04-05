from django.urls import path
from .views import (
    HealthCheckAPIView,
    DeviceListCreateAPIView,
    FrontendLoginAPIView,
    DeviceDashboardCreateAPIView,
    DeviceDashboardAPIView,
)

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="api-health-2"),
    path("auth/login/", FrontendLoginAPIView.as_view(), name="frontend-login"),
    path("devices/", DeviceListCreateAPIView.as_view(), name="device-list-create"),

    path("dashboard/", DeviceDashboardAPIView.as_view(), name="dashboard-list"),
    path("dashboard/<int:device_id>/", DeviceDashboardAPIView.as_view(), name="dashboard-detail"),
    path("dashboard/create/", DeviceDashboardCreateAPIView.as_view(), name="dashboard-create"),

    path("measurements/", DeviceDashboardCreateAPIView.as_view(), name="measurement-create"),
    path("predict/", DeviceDashboardCreateAPIView.as_view(), name="predict-create"),
    path("analyze/", DeviceDashboardCreateAPIView.as_view(), name="analyze-create"),
]