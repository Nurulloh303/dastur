import json
import math
import re

import google.generativeai as genai
from django.conf import settings

from .models import AI_Prediction


class GeminiPredictionError(Exception):
    pass


class FormulaCalculationService:
    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_list(values):
        if not values:
            return []
        result = []
        for item in values:
            try:
                result.append(float(item))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _safe_max_abs_diff(values, ref):
        if not values:
            return 0.0
        return max(abs(float(ref) - float(x)) for x in values)

    @staticmethod
    def calculate_from_measurement(measurement):
        data = measurement.sensor_data or {}

        t_ind_list = FormulaCalculationService._safe_list(
            data.get("indication_temperatures", [])
        )
        chamber_temps = FormulaCalculationService._safe_list(
            data.get("chamber_temperatures", [])
        )

        t_ref = FormulaCalculationService._safe_float(data.get("t_ref"), None)
        t_ref_load = FormulaCalculationService._safe_float(data.get("t_ref_load"), None)
        t_le = FormulaCalculationService._safe_float(data.get("t_le"), None)
        t_he = FormulaCalculationService._safe_float(data.get("t_he"), None)
        u_cal_std = FormulaCalculationService._safe_float(data.get("u_cal_std"), None)
        re_std = FormulaCalculationService._safe_float(data.get("re_std"), None)

        if not t_ind_list:
            t_ind_list = [FormulaCalculationService._safe_float(measurement.temperature, 0.0)]

        n = len(t_ind_list)

        t_ind_avg = sum(t_ind_list) / n if n else 0.0

        if n > 1:
            numerator = sum((x - t_ind_avg) ** 2 for x in t_ind_list)
            u_t_ind = math.sqrt(numerator / (n * (n - 1)))
        else:
            u_t_ind = 0.0

        if not chamber_temps:
            chamber_temps = t_ind_list[:]

        t_bar = sum(chamber_temps) / len(chamber_temps) if chamber_temps else 0.0

        u_instab = (1 / math.sqrt(3)) * FormulaCalculationService._safe_max_abs_diff(
            chamber_temps, t_bar
        )

        u_inhom = 0.0
        if t_ref is not None:
            u_inhom = (1 / math.sqrt(3)) * FormulaCalculationService._safe_max_abs_diff(
                chamber_temps, t_ref
            )

        u_radiation = 0.0
        if t_le is not None and t_he is not None:
            u_radiation = (0.2 / math.sqrt(3)) * abs(t_le - t_he)

        u_load = 0.0
        if t_ref is not None and t_ref_load is not None:
            u_load = (0.2 / math.sqrt(3)) * abs(t_ref - t_ref_load)

        u_cal_std_value = (u_cal_std / 2.0) if u_cal_std is not None else 0.0
        u_rec_std = (re_std / (2 * math.sqrt(3))) if re_std is not None else 0.0

        u_combined = math.sqrt(
            u_t_ind ** 2 +
            u_instab ** 2 +
            u_inhom ** 2 +
            u_radiation ** 2 +
            u_load ** 2 +
            u_cal_std_value ** 2 +
            u_rec_std ** 2
        )

        expanded_uncertainty = 2 * u_combined

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
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        model_name = getattr(settings, "GEMINI_MODEL", None)

        if not api_key:
            raise GeminiPredictionError("GEMINI_API_KEY topilmadi.")
        if not model_name:
            raise GeminiPredictionError("GEMINI_MODEL topilmadi.")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def _build_prompt(self, device, measurement_data, formula_result):
        return f"""
Siz metrologiya va harorat kamerasi monitoringi bo'yicha mutaxassissiz.

Qurilma:
- Nomi: {device.name}
- Turi: {device.device_type}
- Serial: {device.serial_number}

O'lchov ma'lumotlari:
{json.dumps(measurement_data, ensure_ascii=False)}

Formula hisoblash natijalari:
{json.dumps(formula_result, ensure_ascii=False)}

Qoidalar:
1. Statusni o'zgartirmang.
2. Failure probability ni o'zgartirmang.
3. Faqat qisqa tavsiya yozing.
4. Hech qanday warning, reklama, API notice yozmang.
5. Faqat JSON qaytaring.

Kerakli format:
{{
  "advice": "qisqa va aniq tavsiya"
}}
"""

    def _parse_response(self, raw_text):
        cleaned = (raw_text or "").strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        bad_phrases = [
            "IMPORTANT NOTICE",
            "deprecated",
            "legacy text api",
            "migrate to our new service",
        ]

        if any(p.lower() in cleaned.lower() for p in bad_phrases):
            return {
                "advice": "AI xizmati noto‘g‘ri formatdagi javob qaytardi. Formula natijasiga ko‘ra kuzatuv davom ettirilsin.",
                "raw": {"raw_text": raw_text},
            }

        try:
            data = json.loads(cleaned)
            return {
                "advice": str(data.get("advice", "")).strip() or "AI tavsiya topilmadi.",
                "raw": data,
            }
        except Exception:
            return {
                "advice": "AI javobini JSON formatda ajratib bo‘lmadi. Formula natijasiga tayangan holda davom etildi.",
                "raw": {"raw_text": raw_text},
            }

    def analyze_device(self, device, measurement=None):
        if measurement is None:
            measurement = device.measurements.order_by("-created_at").first()

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

        parsed = {
            "advice": "Formula natijalariga ko‘ra qurilmani kuzatishda davom eting.",
            "raw": {},
        }

        try:
            prompt = self._build_prompt(device, measurement_data, formula_result)
            response = self.model.generate_content(prompt)
            response_text = getattr(response, "text", "") or ""
            parsed = self._parse_response(response_text)
        except Exception as exc:
            parsed = {
                "advice": f"AI tavsiya olishda xatolik bo‘ldi: {exc}",
                "raw": {"error": str(exc)},
            }

        return AI_Prediction.objects.create(
            device=device,
            measurement=measurement,
            gemini_response=parsed["raw"],
            calculation_result=formula_result,
            failure_probability=formula_result["failure_prob"],
            advice=parsed["advice"],
            status=formula_result["status"],
        )