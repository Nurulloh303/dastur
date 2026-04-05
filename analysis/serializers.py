from django.utils import timezone
from rest_framework import serializers

from .models import Device, Measurement, AI_Prediction


class DeviceSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="device_type", read_only=True)
    serial = serializers.CharField(source="serial_number", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "name",
            "serial_number",
            "serial",
            "device_type",
            "type",
            "location",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "serial",
            "type",
            "created_at",
        ]


class MeasurementCreateSerializer(serializers.Serializer):
    # Device identification
    device = serializers.IntegerField(required=False)
    device_id = serializers.IntegerField(required=False)

    serial_number = serializers.CharField(required=False, allow_blank=True)
    serial = serializers.CharField(required=False, allow_blank=True)

    name = serializers.CharField(required=False, allow_blank=True)
    device_name = serializers.CharField(required=False, allow_blank=True)

    device_type = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)

    location = serializers.CharField(required=False, allow_blank=True)

    # Main measurements
    temperature = serializers.FloatField(required=False)
    temp = serializers.FloatField(required=False)

    humidity = serializers.FloatField(required=False, allow_null=True)
    humid = serializers.FloatField(required=False, allow_null=True)

    power_usage = serializers.FloatField(required=False, allow_null=True)
    power = serializers.FloatField(required=False, allow_null=True)
    energy = serializers.FloatField(required=False, allow_null=True)

    timestamp = serializers.DateTimeField(required=False)

    # Additional sensor payload
    sensor_data = serializers.JSONField(required=False)
    sensor_values = serializers.JSONField(required=False)
    sensors = serializers.JSONField(required=False)

    # Formula fields
    indication_temperatures = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        allow_empty=True,
    )
    chamber_temperatures = serializers.ListField(
        child=serializers.FloatField(),
        required=False,
        allow_empty=True,
    )
    t_ref = serializers.FloatField(required=False, allow_null=True)
    t_ref_load = serializers.FloatField(required=False, allow_null=True)
    t_le = serializers.FloatField(required=False, allow_null=True)
    t_he = serializers.FloatField(required=False, allow_null=True)
    u_cal_std = serializers.FloatField(required=False, allow_null=True)
    re_std = serializers.FloatField(required=False, allow_null=True)

    def validate(self, attrs):
        resolved_temperature = attrs.get("temperature", attrs.get("temp"))
        resolved_humidity = attrs.get("humidity", attrs.get("humid", None))
        resolved_power_usage = attrs.get(
            "power_usage",
            attrs.get("power", attrs.get("energy", None))
        )

        resolved_sensor_data = attrs.get(
            "sensor_data",
            attrs.get("sensor_values", attrs.get("sensors", {}))
        ) or {}

        resolved_device_id = attrs.get("device", attrs.get("device_id"))
        resolved_name = attrs.get("name", attrs.get("device_name"))
        resolved_serial_number = attrs.get("serial_number", attrs.get("serial"))
        resolved_device_type = attrs.get("device_type", attrs.get("type", Device.THERMOSTAT))
        resolved_location = attrs.get("location", "")

        if resolved_temperature is None:
            raise serializers.ValidationError({
                "temperature": "temperature yoki temp maydoni yuborilishi kerak."
            })

        if not resolved_device_id and not resolved_serial_number and not resolved_name:
            raise serializers.ValidationError({
                "device": "device_id yoki serial_number yoki name yuborilishi kerak."
            })

        formula_fields = [
            "indication_temperatures",
            "chamber_temperatures",
            "t_ref",
            "t_ref_load",
            "t_le",
            "t_he",
            "u_cal_std",
            "re_std",
        ]

        provided_formula_fields = [
            field for field in formula_fields
            if attrs.get(field) is not None and attrs.get(field) != []
        ]

        attrs["resolved_temperature"] = resolved_temperature
        attrs["resolved_humidity"] = resolved_humidity
        attrs["resolved_power_usage"] = resolved_power_usage
        attrs["resolved_sensor_data"] = resolved_sensor_data

        attrs["resolved_device_id"] = resolved_device_id
        attrs["resolved_name"] = resolved_name
        attrs["resolved_serial_number"] = resolved_serial_number
        attrs["resolved_device_type"] = resolved_device_type
        attrs["resolved_location"] = resolved_location

        attrs["formula_completeness"] = {
            "provided_count": len(provided_formula_fields),
            "provided_fields": provided_formula_fields,
        }

        return attrs

    def _normalize_device_type(self, value):
        device_type = str(value or "").strip().lower()

        mapping = {
            "thermostat": Device.THERMOSTAT,
            "termostat": Device.THERMOSTAT,
            "harorat kamerasi": Device.THERMOSTAT,
            "drying cabinet": Device.DRYING_CABINET,
            "drying_cabinet": Device.DRYING_CABINET,
            "quritish shkafi": Device.DRYING_CABINET,
        }

        return mapping.get(device_type, Device.THERMOSTAT)

    def create(self, validated_data):
        device = None

        resolved_device_id = validated_data.get("resolved_device_id")
        resolved_serial_number = validated_data.get("resolved_serial_number")
        resolved_name = validated_data.get("resolved_name")
        resolved_device_type = self._normalize_device_type(
            validated_data.get("resolved_device_type")
        )
        resolved_location = validated_data.get("resolved_location", "")

        if resolved_device_id:
            device = Device.objects.filter(pk=resolved_device_id).first()

        if device is None and resolved_serial_number:
            device = Device.objects.filter(serial_number=resolved_serial_number).first()

        if device is None:
            serial_number = resolved_serial_number or (
                f"AUTO-{(resolved_name or 'DEVICE').upper().replace(' ', '-')}"
            )

            device, _ = Device.objects.get_or_create(
                serial_number=serial_number,
                defaults={
                    "name": resolved_name or "AI Device",
                    "device_type": resolved_device_type,
                    "location": resolved_location,
                },
            )

        updated_fields = []

        if resolved_name and device.name != resolved_name:
            device.name = resolved_name
            updated_fields.append("name")

        if resolved_device_type and getattr(device, "device_type", None) != resolved_device_type:
            device.device_type = resolved_device_type
            updated_fields.append("device_type")

        if resolved_location is not None and hasattr(device, "location") and device.location != resolved_location:
            device.location = resolved_location
            updated_fields.append("location")

        if updated_fields:
            device.save(update_fields=updated_fields)

        formula_payload = {
            "indication_temperatures": validated_data.get("indication_temperatures", []),
            "chamber_temperatures": validated_data.get("chamber_temperatures", []),
            "t_ref": validated_data.get("t_ref"),
            "t_ref_load": validated_data.get("t_ref_load"),
            "t_le": validated_data.get("t_le"),
            "t_he": validated_data.get("t_he"),
            "u_cal_std": validated_data.get("u_cal_std"),
            "re_std": validated_data.get("re_std"),
            "formula_completeness": validated_data.get("formula_completeness", {}),
        }

        merged_sensor_data = dict(validated_data.get("resolved_sensor_data", {}))
        merged_sensor_data.update(formula_payload)

        measurement = Measurement.objects.create(
            device=device,
            temperature=validated_data["resolved_temperature"],
            humidity=validated_data.get("resolved_humidity"),
            power_usage=validated_data.get("resolved_power_usage"),
            sensor_data=merged_sensor_data,
            timestamp=validated_data.get("timestamp") or timezone.now(),
        )
        return measurement


class MeasurementSerializer(serializers.ModelSerializer):
    device = DeviceSerializer(read_only=True)
    device_id = serializers.IntegerField(source="device.id", read_only=True)

    temp = serializers.FloatField(source="temperature", read_only=True)
    humid = serializers.FloatField(source="humidity", read_only=True)
    power = serializers.FloatField(source="power_usage", read_only=True)
    sensors = serializers.JSONField(source="sensor_data", read_only=True)

    class Meta:
        model = Measurement
        fields = [
            "id",
            "device",
            "device_id",
            "temperature",
            "temp",
            "humidity",
            "humid",
            "power_usage",
            "power",
            "timestamp",
            "sensor_data",
            "sensors",
            "created_at",
        ]
        read_only_fields = fields


class AIPredictionSerializer(serializers.ModelSerializer):
    failure_prob = serializers.FloatField(source="failure_probability", read_only=True)
    recommendation = serializers.CharField(source="advice", read_only=True)
    status_label = serializers.CharField(source="status", read_only=True)

    class Meta:
        model = AI_Prediction
        fields = [
            "id",
            "device",
            "measurement",
            "gemini_response",
            "calculation_result",
            "failure_probability",
            "failure_prob",
            "advice",
            "recommendation",
            "status",
            "status_label",
            "created_at",
        ]
        read_only_fields = fields


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField()

    def validate(self, attrs):
        if not attrs.get("username") and not attrs.get("email"):
            raise serializers.ValidationError(
                "username yoki email yuborilishi kerak."
            )
        return attrs


class LoginResponseUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    token = serializers.CharField()
    user = LoginResponseUserSerializer()


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()


class MeasurementCreateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()
    serial_number = serializers.CharField()
    measurement_id = serializers.IntegerField()
    status = serializers.CharField()
    failure_probability = serializers.FloatField()
    advice = serializers.CharField()
    calculation_result = serializers.JSONField()
    gemini_response = serializers.JSONField()
    prediction = AIPredictionSerializer()


class DeviceDashboardSerializer(serializers.Serializer):
    device = DeviceSerializer()
    total_measurements = serializers.IntegerField()
    latest_measurement = MeasurementSerializer(allow_null=True)
    latest_prediction = AIPredictionSerializer(allow_null=True)
    overall_status = serializers.CharField()
    status = serializers.CharField()
    failure_prob = serializers.FloatField()
    advice = serializers.CharField()
    calculation_result = serializers.JSONField()