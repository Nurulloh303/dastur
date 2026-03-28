import json
import re
import google.generativeai as genai
from django.conf import settings
from .models import Device, AI_Prediction


class GeminiPredictionError(Exception):
    pass


class GeminiService:
    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise GeminiPredictionError('GEMINI_API_KEY topilmadi. .env faylini tekshiring.')
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def _build_prompt(self, device: Device, measurements_data: list[dict]) -> str:
        device_label = 'termostat' if device.device_type == Device.THERMOSTAT else 'quritish shkafi'
        return (
            f"Siz metrologiya mutaxassisiz. Quyidagi {device_label} ko'rsatkichlarini tahlil qiling: "
            f"{json.dumps(measurements_data, ensure_ascii=False, default=str)}. "
            "Kelajakda qanday nosozlik bo'lishi mumkin va aniqlik darajasi qanday? "
            "Javobni faqat JSON formatida qaytaring: "
            '{"status": "healthy|warning|critical", "failure_prob": 0-100, "advice": "qisqa tavsiya"}.'
        )

    def _parse_response(self, raw_text: str) -> dict:
        cleaned = raw_text.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GeminiPredictionError(f'Gemini JSON formatda javob qaytarmadi: {raw_text}') from exc

        status = str(data.get('status', AI_Prediction.STATUS_UNKNOWN)).lower().strip()
        if status not in {AI_Prediction.STATUS_HEALTHY, AI_Prediction.STATUS_WARNING, AI_Prediction.STATUS_CRITICAL}:
            status = AI_Prediction.STATUS_UNKNOWN

        try:
            failure_prob = float(data.get('failure_prob', 0))
        except (TypeError, ValueError):
            failure_prob = 0.0
        failure_prob = max(0.0, min(100.0, failure_prob))

        return {
            'status': status,
            'failure_prob': failure_prob,
            'advice': str(data.get('advice', '')).strip(),
            'raw': data,
        }

    def analyze_device(self, device: Device, measurement=None) -> AI_Prediction:
        latest_measurements = list(
            device.measurements.order_by('-timestamp').values(
                'temperature', 'humidity', 'timestamp', 'power_usage', 'sensor_data'
            )[:10]
        )
        if not latest_measurements:
            raise GeminiPredictionError("Tahlil uchun o'lchovlar topilmadi.")

        prompt = self._build_prompt(device, latest_measurements)
        response = self.model.generate_content(prompt)
        response_text = getattr(response, 'text', '') or ''
        parsed = self._parse_response(response_text)

        return AI_Prediction.objects.create(
            device=device,
            measurement=measurement,
            gemini_response=parsed['raw'],
            failure_probability=parsed['failure_prob'],
            advice=parsed['advice'],
            status=parsed['status'],
        )
