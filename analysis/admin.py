from django.contrib import admin
from .models import Device, Measurement, AI_Prediction


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "serial_number", "device_type", "created_at")
    search_fields = ("name", "serial_number")
    list_filter = ("device_type",)


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "temperature", "humidity", "power_usage", "timestamp")
    search_fields = ("device__name", "device__serial_number")
    list_filter = ("timestamp", "device__device_type")


@admin.register(AI_Prediction)
class AIPredictionAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "status", "failure_probability", "created_at")
    search_fields = ("device__name", "device__serial_number", "status")
    list_filter = ("created_at", "status")

    def has_add_permission(self, request):
        return False