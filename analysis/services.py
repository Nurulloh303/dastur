import json
import math
import re

import google.generativeai as genai
from django.conf import settings

from .models import Device, AI_Prediction


class GeminiPredictionError(Exception):
    pass


class FormulaCalculationService:
    @staticmethod
    def _safe_max_abs_diff(values, ref):
        if not values:
            return 0.0
        return max(abs(ref - x) for x in values)

    @staticmethod
    def calculate_from_measurement(measurement):
        data = measurement.sensor_data or {}

        t_ind_list = data.get("indication_temperatures", []) or []
        chamber_temps = data.get("chamber_temperatures", []) or []

        t_ref = data.get("t_ref")
        t_ref_load = data.get("t_ref_load")
        t_le = data.get("t_le")
        t_he = data.get("t_he")
        u_cal_std = data.get("u_cal_std")
        re_std = data.get("re_std")

        if not t_ind_list:
            t_ind_list = [measurement.temperature]

        n = len(t_ind_list)

        # (8)
        t_ind_avg = sum(t_ind_list) / n if n else 0.0

        # (9)
        if n > 1:
            numerator = sum((x - t_ind_avg) ** 2 for x in t_ind_list)
            u_t_ind = math.sqrt(numerator / (n * (n - 1)))
        else:
            u_t_ind = 0.0

        if not chamber_temps:
            chamber_temps = t_ind_list

        t_bar = sum(chamber_temps) / len(chamber_temps) if chamber_temps else 0.0

        # (10)
        u_instab = (1 / math.sqrt(3)) * FormulaCalculationService._safe_max_abs_diff(chamber_temps, t_bar)

        # (11)
        u_inhom = 0.0
        if t_ref is not None:
            u_inhom = (1 / math.sqrt(3)) * FormulaCalculationService._safe_max_abs_diff(chamber_temps, float(t_ref))

        # (12)
        u_radiation = 0.0
        if t_le is not None and t_he is not None:
            u_radiation = (0.2 / math.sqrt(3)) * abs(float(t_le) - float(t_he))

        # (13)
        u_load = 0.0
        if t_ref is not None and t_ref_load is not None:
            u_load = (0.2 / math.sqrt(3)) * abs(float(t_ref) - float(t_ref_load))

        # (14)
        u_cal_std_value = (float(u_cal_std) / 2.0) if u_cal_std is not None else 0.0

        # (15)
        u_rec_std = (float(re_std) / (2 * math.sqrt(3))) if re_std is not None else 0.0

        # Combined standard uncertainty
        u_combined = math.sqrt(
            u_t_ind ** 2 +
            u_instab ** 2 +
            u_inhom ** 2 +
            u_radiation ** 2 +
            u_load ** 2 +
            u_cal_std_value ** 2 +
            u_rec_std ** 2
        )

        # Expanded uncertainty (k=2)
        expanded_uncertainty = 2 * u_combined

        # Temporary business rule
        if expanded_uncertainty < 0.5:
            status = AI_Prediction.STATUS_HEALTHY
            failure_prob = 15.0
        elif expanded_uncertainty < 1.5:
            status = AI_Prediction.STATUS_WARNING
            failure_prob = 55.0
        else:
            status = AI_Prediction.STATUS_CRITICAL
            failure_prob = 85.0

        return {
            "t_ind_avg": round(t_ind_avg, 6),
            "u_t_ind": round(u_t_ind, 6),
            "u_instab": round(u_instab, 6),
            "u_inhom": round(u_inhom, 6),
            "u_radiation": round(u_radiation, 6),
            "u_load": round(u_load, 6),
            "u_cal_std": round(u_cal_std_value, 6),
            "u_rec_std": round(u_rec_std, 6),
            "u_combined": round(u_combined, 6),
            "expanded_uncertainty": round(expanded_uncertainty, 6),
            "status": status,
            "failure_prob": round(failure_prob, 2),
        }


class GeminiService:
    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise GeminiPredictionError("GEMINI_API_KEY topilmadi. .env faylini tekshiring.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def _build_prompt(self, device: Device, measurement_data: dict, formula_result: dict) -> str:
        device_label = "termostat" if device.device_type == Device.THERMOSTAT else "quritish shkafi"

        return (
            f"Siz metrologiya va sanoat uskunalari bo‘yicha mutaxassissiz.\n"
            f"Qurilma turi: {device_label}\n"
            f"O‘lchov ma’lumotlari: {json.dumps(measurement_data, ensure_ascii=False, default=str)}\n"
            f"Formulalar bo‘yicha hisoblangan natijalar: {json.dumps(formula_result, ensure_ascii=False, default=str)}\n\n"
            f"Diqqat: status va failure_prob ni formuladan kelgan qiymatlarga zid qilmay izoh bering.\n"
            f"Javobni faqat JSON ko‘rinishda qaytaring:\n"
            f'{{"status":"healthy|warning|critical|unknown","failure_prob":0-100,"advice":"qisqa tavsiya"}}'
        )

    def _parse_response(self, raw_text: str) -> dict:
        cleaned = raw_text.strip()
        cleaned = re.sub(r'^```json\s*', '', cleaned)
        cleaned = re.sub(r'^```\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "status": AI_Prediction.STATUS_UNKNOWN,
                "failure_prob": 0.0,
                "advice": "AI javobini JSON formatda ajratib bo‘lmadi.",
                "raw": {"raw_text": raw_text},
            }

        status = str(data.get("status", AI_Prediction.STATUS_UNKNOWN)).lower().strip()
        if status not in {
            AI_Prediction.STATUS_HEALTHY,
            AI_Prediction.STATUS_WARNING,
            AI_Prediction.STATUS_CRITICAL,
            AI_Prediction.STATUS_UNKNOWN,
        }:
            status = AI_Prediction.STATUS_UNKNOWN

        try:
            failure_prob = float(data.get("failure_prob", 0))
        except (TypeError, ValueError):
            failure_prob = 0.0

        failure_prob = max(0.0, min(100.0, failure_prob))

        return {
            "status": status,
            "failure_prob": failure_prob,
            "advice": str(data.get("advice", "")).strip(),
            "raw": data,
        }

    def analyze_device(self, device: Device, measurement=None) -> AI_Prediction:
        if measurement is None:
            measurement = device.measurements.order_by('-created_at').first()

        if measurement is None:
            raise GeminiPredictionError("Tahlil uchun measurement topilmadi.")

        formula_result = FormulaCalculationService.calculate_from_measurement(measurement)

        measurement_data = {
            "temperature": measurement.temperature,
            "humidity": measurement.humidity,
            "power_usage": measurement.power_usage,
            "sensor_data": measurement.sensor_data,
            "timestamp": str(measurement.timestamp),
        }

        prompt = self._build_prompt(device, measurement_data, formula_result)
        response = self.model.generate_content(prompt)
        response_text = getattr(response, "text", "") or ""
        parsed = self._parse_response(response_text)

        return AI_Prediction.objects.create(
            device=device,
            measurement=measurement,
            gemini_response=parsed["raw"],
            calculation_result=formula_result,
            failure_probability=formula_result["failure_prob"],
            advice=parsed["advice"] or "Formula natijalariga ko‘ra kuzatuvni davom ettiring.",
            status=formula_result["status"],
        )