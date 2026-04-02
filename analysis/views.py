from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Device
from .serializers import (
    FlexibleMeasurementCreateSerializer,
    MeasurementSerializer,
    AIPredictionSerializer,
    DeviceSerializer,
    LoginRequestSerializer,
    LoginResponseSerializer,
    HealthCheckSerializer,
    MeasurementCreateResponseSerializer,
    DeviceDashboardSerializer,
)
from .services import GeminiService, GeminiPredictionError


@extend_schema(
    tags=['System'],
    responses={200: HealthCheckSerializer},
    description='API sog‘lom ishlayotganini tekshiradi.',
)
class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(
            {'status': 'ok', 'service': 'DGU 53519 API'},
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Devices'],
    responses={200: DeviceSerializer(many=True)},
    description='Barcha uskunalar ro‘yxatini qaytaradi.',
)
class DeviceListCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        devices = Device.objects.all().order_by('-created_at')
        return Response(DeviceSerializer(devices, many=True).data)

    @extend_schema(
        request=DeviceSerializer,
        responses={201: DeviceSerializer},
        description='Yangi uskuna yaratadi.',
        examples=[
            OpenApiExample(
                'Device create example',
                value={
                    'name': 'Termostat 1',
                    'serial_number': 'TH-001',
                    'device_type': 'thermostat'
                },
                request_only=True,
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = DeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = serializer.save()
        return Response(DeviceSerializer(device).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Auth'],
    request=LoginRequestSerializer,
    responses={
        200: LoginResponseSerializer,
        401: None,
    },
    description='Username/email va password orqali JWT token qaytaradi.',
    examples=[
        OpenApiExample(
            'Login example',
            value={
                'username': 'admin',
                'password': 'your_password'
            },
            request_only=True,
        )
    ],
)
class FrontendLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get('username') or request.data.get('email')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {'detail': 'Login yoki parol noto‘g‘ri.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'token': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
            },
        })


@extend_schema(
    tags=['Measurements'],
    request=FlexibleMeasurementCreateSerializer,
    responses={
        201: MeasurementCreateResponseSerializer,
        502: None,
        500: None,
    },
    description='Yangi measurement qabul qiladi va avtomatik AI tahlilni ishga tushiradi.',
    examples=[
        OpenApiExample(
            'Measurement request example',
            value={
                'device_id': 1,
                'temperature': 37.5,
                'humidity': 45.0,
                'power_usage': 220.0,
                'sensor_data': {
                    'sensor_1': 37.2,
                    'sensor_2': 37.8
                }
            },
            request_only=True,
        ),
        OpenApiExample(
            'Flexible frontend example',
            value={
                'serial': 'TH-001',
                'temp': 38.1,
                'humid': 42.0,
                'power': 210.0,
                'sensors': {
                    'ch1': 38.0,
                    'ch2': 38.3
                },
                'indication_temperatures': [38.0, 38.1, 38.2],
                'chamber_temperatures': [37.9, 38.1, 38.3],
                't_ref': 38.0,
                't_ref_load': 37.8,
                't_le': 37.9,
                't_he': 38.2,
                'u_cal_std': 0.2,
                're_std': 0.1
            },
            request_only=True,
        ),
    ],
)
class MeasurementCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = FlexibleMeasurementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        measurement = serializer.save()

        try:
            prediction = GeminiService().analyze_device(
                device=measurement.device,
                measurement=measurement
            )
        except GeminiPredictionError as exc:
            measurement.delete()
            return Response(
                {
                    'detail': 'AI tahlilni bajarishda xatolik yuz berdi.',
                    'error': str(exc)
                },
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as exc:
            measurement.delete()
            return Response(
                {
                    'detail': 'Kutilmagan server xatoligi.',
                    'error': str(exc)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        measurement_data = MeasurementSerializer(measurement).data
        prediction_data = AIPredictionSerializer(prediction).data
        device_data = DeviceSerializer(measurement.device).data

        return Response({
            'message': 'Measurement saved and analyzed successfully.',
            'measurement': measurement_data,
            'prediction': prediction_data,
            'ai_prediction': prediction_data,
            'device': device_data,
            'status': prediction.status,
            'failure_prob': prediction.failure_probability,
            'advice': prediction.advice,
            'calculation_result': prediction.calculation_result,
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Dashboard'],
    parameters=[
        OpenApiParameter(name='device_id', required=False, type=int, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='serial', required=False, type=str, location=OpenApiParameter.QUERY),
        OpenApiParameter(name='serial_number', required=False, type=str, location=OpenApiParameter.QUERY),
    ],
    responses={200: DeviceDashboardSerializer},
    description='Uskunaning umumiy holati, oxirgi measurement va oxirgi AI prediction ma’lumotini qaytaradi.',
)
class DeviceDashboardAPIView(APIView):
    permission_classes = [AllowAny]

    def get_device(self, request, device_id=None):
        query_device_id = device_id or request.query_params.get('device_id')
        serial = request.query_params.get('serial') or request.query_params.get('serial_number')

        if query_device_id:
            return get_object_or_404(Device, pk=query_device_id)

        if serial:
            return get_object_or_404(Device, serial_number=serial)

        latest = Device.objects.order_by('-created_at').first()
        return latest

    def get(self, request, device_id=None, *args, **kwargs):
        device = self.get_device(request, device_id)

        if device is None:
            return Response(
                {'detail': 'Hali hech qanday uskuna yaratilmagan.'},
                status=status.HTTP_404_NOT_FOUND
            )

        latest_measurement = device.measurements.order_by('-timestamp', '-created_at').first()
        latest_prediction = device.predictions.order_by('-created_at').first()

        payload = {
            'device': DeviceSerializer(device).data,
            'total_measurements': device.measurements.count(),
            'latest_measurement': MeasurementSerializer(latest_measurement).data if latest_measurement else None,
            'latest_prediction': AIPredictionSerializer(latest_prediction).data if latest_prediction else None,
            'overall_status': latest_prediction.status if latest_prediction else 'unknown',
            'status': latest_prediction.status if latest_prediction else 'unknown',
            'failure_prob': latest_prediction.failure_probability if latest_prediction else 0,
            'advice': latest_prediction.advice if latest_prediction else '',
            'calculation_result': latest_prediction.calculation_result if latest_prediction else {},
        }
        return Response(payload, status=status.HTTP_200_OK)