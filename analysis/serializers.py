from rest_framework import serializers
from .models import Device, Measurement, AI_Prediction


class DeviceSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='device_type', read_only=True)
    serial = serializers.CharField(source='serial_number', read_only=True)

    class Meta:
        model = Device
        fields = [
            'id',
            'name',
            'serial_number',
            'serial',
            'device_type',
            'type',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'serial', 'type']


class FlexibleMeasurementCreateSerializer(serializers.Serializer):
    device = serializers.IntegerField(required=False)
    device_id = serializers.IntegerField(required=False)

    temperature = serializers.FloatField(required=False)
    temp = serializers.FloatField(required=False)

    humidity = serializers.FloatField(required=False)
    humid = serializers.FloatField(required=False)

    power_usage = serializers.FloatField(required=False)
    power = serializers.FloatField(required=False)
    energy = serializers.FloatField(required=False)

    timestamp = serializers.DateTimeField(required=False)

    sensor_data = serializers.JSONField(required=False)
    sensor_values = serializers.JSONField(required=False)
    sensors = serializers.JSONField(required=False)

    device_name = serializers.CharField(required=False)
    name = serializers.CharField(required=False)

    serial_number = serializers.CharField(required=False)
    serial = serializers.CharField(required=False)

    device_type = serializers.CharField(required=False)
    type = serializers.CharField(required=False)

    def validate(self, attrs):
        resolved_temperature = attrs.get('temperature', attrs.get('temp'))
        resolved_humidity = attrs.get('humidity', attrs.get('humid', 0.0))
        resolved_power_usage = attrs.get('power_usage', attrs.get('power', attrs.get('energy', 0.0)))
        resolved_sensor_data = attrs.get('sensor_data', attrs.get('sensor_values', attrs.get('sensors', {}))) or {}

        resolved_device_id = attrs.get('device', attrs.get('device_id'))
        resolved_device_name = attrs.get('device_name', attrs.get('name'))
        resolved_serial_number = attrs.get('serial_number', attrs.get('serial'))
        resolved_device_type = attrs.get('device_type', attrs.get('type', Device.THERMOSTAT))

        if resolved_temperature is None:
            raise serializers.ValidationError({
                'temperature': 'temperature yoki temp maydoni yuborilishi kerak.'
            })

        if not resolved_device_id and not resolved_serial_number and not resolved_device_name:
            raise serializers.ValidationError({
                'device': 'device_id yoki serial_number yoki device_name yuborilishi kerak.'
            })

        attrs['resolved_temperature'] = resolved_temperature
        attrs['resolved_humidity'] = resolved_humidity
        attrs['resolved_power_usage'] = resolved_power_usage
        attrs['resolved_sensor_data'] = resolved_sensor_data
        attrs['resolved_device_id'] = resolved_device_id
        attrs['resolved_device_name'] = resolved_device_name
        attrs['resolved_serial_number'] = resolved_serial_number
        attrs['resolved_device_type'] = resolved_device_type

        return attrs

    def create(self, validated_data):
        device = None
        resolved_device_id = validated_data.get('resolved_device_id')
        resolved_serial_number = validated_data.get('resolved_serial_number')
        resolved_device_name = validated_data.get('resolved_device_name')
        resolved_device_type = validated_data.get('resolved_device_type')

        if resolved_device_id:
            device = Device.objects.filter(pk=resolved_device_id).first()

        if device is None and resolved_serial_number:
            device = Device.objects.filter(serial_number=resolved_serial_number).first()

        if device is None:
            device_type = str(resolved_device_type).lower().strip()

            if device_type in {'quritish shkafi', 'drying cabinet', 'drying_cabinet'}:
                device_type = Device.DRYING_CABINET
            else:
                device_type = Device.THERMOSTAT

            serial_number = resolved_serial_number or f"AUTO-{(resolved_device_name or 'DEVICE').upper().replace(' ', '-')}"

            device, _ = Device.objects.get_or_create(
                serial_number=serial_number,
                defaults={
                    'name': resolved_device_name or 'AI Device',
                    'device_type': device_type,
                }
            )

            if resolved_device_name and device.name != resolved_device_name:
                device.name = resolved_device_name
                device.save(update_fields=['name'])

        measurement = Measurement.objects.create(
            device=device,
            temperature=validated_data['resolved_temperature'],
            humidity=validated_data['resolved_humidity'],
            power_usage=validated_data['resolved_power_usage'],
            sensor_data=validated_data['resolved_sensor_data'],
            timestamp=validated_data.get('timestamp') if validated_data.get('timestamp') else None,
        )
        return measurement


class MeasurementSerializer(serializers.ModelSerializer):
    device = DeviceSerializer(read_only=True)
    device_id = serializers.IntegerField(source='device.id', read_only=True)

    temp = serializers.FloatField(source='temperature', read_only=True)
    humid = serializers.FloatField(source='humidity', read_only=True)
    power = serializers.FloatField(source='power_usage', read_only=True)
    sensors = serializers.JSONField(source='sensor_data', read_only=True)

    class Meta:
        model = Measurement
        fields = [
            'id',
            'device',
            'device_id',
            'temperature',
            'temp',
            'humidity',
            'humid',
            'timestamp',
            'power_usage',
            'power',
            'sensor_data',
            'sensors',
        ]


class AIPredictionSerializer(serializers.ModelSerializer):
    failure_prob = serializers.FloatField(source='failure_probability', read_only=True)
    recommendation = serializers.CharField(source='advice', read_only=True)
    status_label = serializers.CharField(source='status', read_only=True)

    class Meta:
        model = AI_Prediction
        fields = [
            'id',
            'device',
            'measurement',
            'gemini_response',
            'failure_probability',
            'failure_prob',
            'advice',
            'recommendation',
            'status',
            'status_label',
            'created_at',
        ]
        read_only_fields = fields


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField()


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
    measurement = MeasurementSerializer()
    prediction = AIPredictionSerializer()
    ai_prediction = AIPredictionSerializer()
    device = DeviceSerializer()
    status = serializers.CharField()
    failure_prob = serializers.FloatField()
    advice = serializers.CharField()


class DeviceDashboardSerializer(serializers.Serializer):
    device = DeviceSerializer()
    total_measurements = serializers.IntegerField()
    latest_measurement = MeasurementSerializer(allow_null=True)
    latest_prediction = AIPredictionSerializer(allow_null=True)
    overall_status = serializers.CharField()
    status = serializers.CharField()
    failure_prob = serializers.FloatField()
    advice = serializers.CharField()