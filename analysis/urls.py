from django.urls import path
from .views import (
    HealthCheckAPIView,
    DeviceListCreateAPIView,
    MeasurementCreateAPIView,
    DeviceDashboardAPIView,
    FrontendLoginAPIView,
)

urlpatterns = [
    # 🔹 Health check
    path('', HealthCheckAPIView.as_view(), name='api-health'),
    path('health/', HealthCheckAPIView.as_view(), name='api-health-2'),

    # 🔹 Auth
    path('auth/login/', FrontendLoginAPIView.as_view(), name='frontend-login'),

    # 🔹 Devices
    path('devices/', DeviceListCreateAPIView.as_view(), name='device-list-create'),

    # 🔹 Measurements / AI
    path('measurements/', MeasurementCreateAPIView.as_view(), name='measurement-create'),

    # 👉 Frontend uchun alias endpointlar
    path('predict/', MeasurementCreateAPIView.as_view(), name='predict-create'),
    path('analyze/', MeasurementCreateAPIView.as_view(), name='analyze-create'),

    # 🔹 Dashboard
    path('dashboard/', DeviceDashboardAPIView.as_view(), name='device-dashboard-query'),
    path('dashboard/<int:device_id>/', DeviceDashboardAPIView.as_view(), name='device-dashboard'),

    # 👉 Alternativ (REST style)
    path('devices/<int:device_id>/dashboard/', DeviceDashboardAPIView.as_view(), name='device-dashboard-alt'),
]