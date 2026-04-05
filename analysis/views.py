from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Device, AI_Prediction, Measurement
from .serializers import (
    AIPredictionSerializer,
    DeviceDashboardSerializer,
    DeviceSerializer,
    HealthCheckSerializer,
    LoginRequestSerializer,
    LoginResponseSerializer,
    MeasurementCreateResponseSerializer,
    MeasurementCreateSerializer,
    MeasurementSerializer,
)
from .services import FormulaCalculationService, GeminiService


def build_prediction_with_fallback(measurement):
    try:
        return GeminiService().analyze_device(
            device=measurement.device,
            measurement=measurement,
        )
    except Exception as exc:
        formula_result = FormulaCalculationService.calculate_from_measurement(measurement)

        return AI_Prediction.objects.create(
            device=measurement.device,
            measurement=measurement,
            gemini_response={"error": str(exc)},
            calculation_result=formula_result,
            failure_probability=formula_result["failure_prob"],
            advice="AI tavsiya vaqtincha olinmadi, formula natijasiga ko‘ra kuzatuvni davom ettiring.",
            status=formula_result["status"],
        )


def build_measurement_response(prediction, measurement):
    return {
        "message": "Tahlil muvaffaqiyatli yakunlandi",
        "device_id": measurement.device.id,
        "device_name": measurement.device.name,
        "serial_number": measurement.device.serial_number,
        "measurement_id": measurement.id,
        "status": prediction.status,
        "failure_probability": prediction.failure_probability,
        "advice": prediction.advice,
        "calculation_result": prediction.calculation_result,
        "gemini_response": prediction.gemini_response,
        "prediction": AIPredictionSerializer(prediction).data,
    }


class HealthCheckAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        payload = {
            "status": "ok",
            "service": "DGU AI Analysis API",
        }
        serializer = HealthCheckSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FrontendLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data.get("username")
        email = serializer.validated_data.get("email")
        password = serializer.validated_data["password"]

        user = None
        if username:
            user = authenticate(request, username=username, password=password)

        if user is None and email:
            User = get_user_model()
            user_obj = User.objects.filter(email=email).first()
            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            return Response(
                {"detail": "Login yoki parol noto‘g‘ri."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        response_payload = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "token": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
            },
        }
        output = LoginResponseSerializer(response_payload)
        return Response(output.data, status=status.HTTP_200_OK)


class DeviceListCreateAPIView(generics.ListCreateAPIView):
    queryset = Device.objects.all().order_by("-created_at")
    serializer_class = DeviceSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = DeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        serial_number = validated.get("serial_number")
        if not serial_number:
            return Response(
                {"serial_number": ["Bu maydon majburiy."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        device, created = Device.objects.get_or_create(
            serial_number=serial_number,
            defaults={
                "name": validated.get("name", serial_number),
                "device_type": validated.get("device_type", Device.THERMOSTAT),
                "location": validated.get("location", ""),
                "status": Device.STATUS_ONLINE,
            },
        )

        changed = False
        if validated.get("name") and validated["name"] != device.name:
            device.name = validated["name"]
            changed = True
        if validated.get("device_type") and validated["device_type"] != device.device_type:
            device.device_type = validated["device_type"]
            changed = True
        if "location" in validated and validated.get("location", "") != device.location:
            device.location = validated.get("location", "")
            changed = True
        if device.status != Device.STATUS_ONLINE:
            device.status = Device.STATUS_ONLINE
            changed = True

        if changed:
            device.save()

        return Response(
            DeviceSerializer(device).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class DeviceDashboardCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = MeasurementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        measurement = serializer.save()
        prediction = build_prediction_with_fallback(measurement)

        response_data = build_measurement_response(prediction, measurement)
        output = MeasurementCreateResponseSerializer(response_data)
        return Response(output.data, status=status.HTTP_201_CREATED)


class DeviceDashboardAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, device_id=None, *args, **kwargs):
        if device_id is not None:
            device = Device.objects.filter(pk=device_id).first()
            if device is None:
                return Response(
                    {"detail": "Qurilma topilmadi."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            latest_measurement = device.measurements.order_by("-timestamp", "-created_at").first()
            latest_prediction = device.predictions.order_by("-created_at").first()

            payload = {
                "device": DeviceSerializer(device).data,
                "total_measurements": device.measurements.count(),
                "latest_measurement": MeasurementSerializer(latest_measurement).data if latest_measurement else None,
                "latest_prediction": AIPredictionSerializer(latest_prediction).data if latest_prediction else None,
                "overall_status": latest_prediction.status if latest_prediction else AI_Prediction.STATUS_UNKNOWN,
                "status": latest_prediction.status if latest_prediction else AI_Prediction.STATUS_UNKNOWN,
                "failure_prob": latest_prediction.failure_probability if latest_prediction else 0.0,
                "advice": latest_prediction.advice if latest_prediction else "",
                "calculation_result": latest_prediction.calculation_result if latest_prediction else {},
            }
            output = DeviceDashboardSerializer(payload)
            return Response(output.data, status=status.HTTP_200_OK)

        devices = Device.objects.annotate(total_measurements=Count("measurements")).order_by("-created_at")
        results = []

        for device in devices:
            latest_measurement = device.measurements.order_by("-timestamp", "-created_at").first()
            latest_prediction = device.predictions.order_by("-created_at").first()

            payload = {
                "device": DeviceSerializer(device).data,
                "total_measurements": device.total_measurements,
                "latest_measurement": MeasurementSerializer(latest_measurement).data if latest_measurement else None,
                "latest_prediction": AIPredictionSerializer(latest_prediction).data if latest_prediction else None,
                "overall_status": latest_prediction.status if latest_prediction else AI_Prediction.STATUS_UNKNOWN,
                "status": latest_prediction.status if latest_prediction else AI_Prediction.STATUS_UNKNOWN,
                "failure_prob": latest_prediction.failure_probability if latest_prediction else 0.0,
                "advice": latest_prediction.advice if latest_prediction else "",
                "calculation_result": latest_prediction.calculation_result if latest_prediction else {},
            }
            results.append(DeviceDashboardSerializer(payload).data)

        return Response(results, status=status.HTTP_200_OK)