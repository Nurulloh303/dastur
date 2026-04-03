from django.urls import path
from .views import (
    HealthCheckAPIView,
    DeviceListCreateAPIView,
    FrontendLoginAPIView,
    DeviceDashboardCreateAPIView,
)

urlpatterns = [
    # 🔹 Health check
    path('health/', HealthCheckAPIView.as_view(), name='api-health-2'),

    # 🔹 Auth
    path('auth/login/', FrontendLoginAPIView.as_view(), name='frontend-login'),

    # 🔹 Devices
    path('devices/', DeviceListCreateAPIView.as_view(), name='device-list-create'),

    # 🔥 ASOSIY ENDPOINT (hammasi shu yerda)
    path('dashboard/create/', DeviceDashboardCreateAPIView.as_view(), name='dashboard-create'),

    # 👉 Frontend uchun alias (hammasi bitta viewga boradi)
    path('measurements/', DeviceDashboardCreateAPIView.as_view(), name='measurement-create'),
    path('predict/', DeviceDashboardCreateAPIView.as_view(), name='predict-create'),
    path('analyze/', DeviceDashboardCreateAPIView.as_view(), name='analyze-create'),
]