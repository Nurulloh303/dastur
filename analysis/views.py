from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Device, AI_Prediction, Measurement
from .serializers import MeasurementCreateSerializer, AIPredictionSerializer
from .services import GeminiService, FormulaCalculationService


class MeasurementAnalyzeAPIView(APIView):
    """
    Frontenddan ma'lumot keladi:
    - device topiladi yoki yaratiladi
    - measurement saqlanadi
    - formula hisoblanadi
    - AI tavsiya olinadi
    - AI ishlamasa ham formula natijasi qaytadi
    """

    def post(self, request, *args, **kwargs):
        serializer = MeasurementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        serial_number = data["serial_number"]

        device, _ = Device.objects.get_or_create(
            serial_number=serial_number,
            defaults={
                "name": data.get("name", serial_number),
                "device_type": data.get("device_type", "thermostat"),
                "location": data.get("location", ""),
                "status": Device.STATUS_ONLINE if hasattr(Device, "STATUS_ONLINE") else "online",
            }
        )

        # Agar mavjud bo'lsa yangilab qo'yamiz
        if data.get("name"):
            device.name = data["name"]
        if data.get("device_type"):
            device.device_type = data["device_type"]
        if "location" in data:
            device.location = data.get("location", device.location)
        if hasattr(Device, "STATUS_ONLINE"):
            device.status = Device.STATUS_ONLINE
        else:
            device.status = "online"
        device.save()

        sensor_data = {
            "indication_temperatures": data.get("indication_temperatures", []),
            "chamber_temperatures": data.get("chamber_temperatures", []),
            "t_ref": data.get("t_ref"),
            "t_ref_load": data.get("t_ref_load"),
            "t_le": data.get("t_le"),
            "t_he": data.get("t_he"),
            "u_cal_std": data.get("u_cal_std"),
            "re_std": data.get("re_std"),
        }

        measurement = Measurement.objects.create(
            device=device,
            temperature=data["temperature"],
            humidity=data.get("humidity"),
            power_usage=data.get("power_usage"),
            sensor_data=sensor_data,
        )

        try:
            prediction = GeminiService().analyze_device(
                device=device,
                measurement=measurement
            )
        except Exception as exc:
            formula_result = FormulaCalculationService.calculate_from_measurement(measurement)

            prediction = AI_Prediction.objects.create(
                device=device,
                measurement=measurement,
                gemini_response={"error": str(exc)},
                calculation_result=formula_result,
                failure_probability=formula_result["failure_prob"],
                advice="AI tavsiya vaqtincha olinmadi, formula natijasiga ko‘ra kuzatuvni davom ettiring.",
                status=formula_result["status"],
            )

        response_data = {
            "message": "Tahlil muvaffaqiyatli yakunlandi",
            "device_id": device.id,
            "device_name": device.name,
            "serial_number": device.serial_number,
            "measurement_id": measurement.id,
            "status": prediction.status,
            "failure_probability": prediction.failure_probability,
            "advice": prediction.advice,
            "calculation_result": prediction.calculation_result,
            "gemini_response": prediction.gemini_response,
            "prediction": AIPredictionSerializer(prediction).data,
        }

        return Response(response_data, status=status.HTTP_201_CREATED)