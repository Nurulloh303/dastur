from django.db import models


class Device(models.Model):
    THERMOSTAT = "thermostat"
    DRYING_CABINET = "drying_cabinet"

    DEVICE_TYPES = [
        (THERMOSTAT, "Thermostat"),
        (DRYING_CABINET, "Drying Cabinet"),
    ]

    name = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=100, unique=True)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"


class Measurement(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="measurements")
    temperature = models.FloatField()
    humidity = models.FloatField(null=True, blank=True)
    power_usage = models.FloatField(null=True, blank=True)
    sensor_data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.name} - {self.created_at}"


class AI_Prediction(models.Model):
    STATUS_HEALTHY = "healthy"
    STATUS_WARNING = "warning"
    STATUS_CRITICAL = "critical"
    STATUS_UNKNOWN = "unknown"

    STATUS_CHOICES = [
        (STATUS_HEALTHY, "Healthy"),
        (STATUS_WARNING, "Warning"),
        (STATUS_CRITICAL, "Critical"),
        (STATUS_UNKNOWN, "Unknown"),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="predictions")
    measurement = models.ForeignKey(
        Measurement,
        on_delete=models.CASCADE,
        related_name="predictions",
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_UNKNOWN,
    )
    gemini_response = models.JSONField(default=dict, blank=True)
    failure_probability = models.FloatField(default=0)
    advice = models.TextField(blank=True, default="")
    calculation_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.name} - {self.failure_probability}%"