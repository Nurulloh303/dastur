# DGU № 53519 - Frontend Ready Django API

Bu versiya `https://ailan.netlify.app/` kabi frontendlarga moslashuvchanroq ishlashi uchun qayta yozilgan.

## Nimalar qo'shildi
- PostgreSQL sozlamalari `.env` orqali
- Gemini API `.env` orqali xavfsiz o'qiladi
- CORS qo'shildi (`ailan.netlify.app` ruxsat etilgan)
- Bir nechta frontend formatlarini qabul qiladi:
  - `device` yoki `device_id`
  - `temperature` yoki `temp`
  - `humidity` yoki `humid`
  - `power_usage` yoki `power` yoki `energy`
  - `sensor_data` yoki `sensor_values` yoki `sensors`
  - `serial_number` yoki `serial`
  - `device_type` yoki `type`
- Agar qurilma mavjud bo'lmasa, serial bo'yicha avtomatik yaratiladi
- Qo'shimcha endpointlar qo'shildi: `/predict/`, `/analyze/`, `/devices/`, `/auth/login/`

## O'rnatish
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## PostgreSQL
PostgreSQL da baza yarating:
```sql
CREATE DATABASE dgu_53519;
```

## .env ni to'ldiring
`.env` ichida quyidagilarni kiriting:
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `GEMINI_API_KEY`

## Migratsiya
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

## Ishga tushirish
```bash
python manage.py runserver
```

## Asosiy endpointlar
### 1. Login
`POST /api/v1/auth/login/`
```json
{
  "username": "admin",
  "password": "12345"
}
```

### 2. JWT token olish
`POST /api/token/`

### 3. Device yaratish yoki ro'yxat
`GET/POST /api/v1/devices/`

### 4. Measurement yuborish
`POST /api/v1/measurements/`

Minimal format:
```json
{
  "device_id": 1,
  "temperature": 37.4,
  "humidity": 48.2,
  "power_usage": 4.1,
  "sensor_data": {"vibration": 0.2, "voltage": 219}
}
```

Frontendga mos variant:
```json
{
  "name": "Termostat A1",
  "serial": "TH-001",
  "type": "thermostat",
  "temp": 37.4,
  "humid": 48.2,
  "power": 4.1,
  "sensors": {"vibration": 0.2, "voltage": 219}
}
```

### 5. Dashboard
- `GET /api/v1/dashboard/1/`
- `GET /api/v1/dashboard/?device_id=1`
- `GET /api/v1/devices/1/dashboard/`

## Netlify frontend uchun
Agar backend boshqa domenda tursa, `.env` da `CORS_ALLOWED_ORIGINS` ichida frontend domeni bo'lishi shart.

## Muhim eslatma
Men frontendning ichki JavaScript request kodini to'liq ko'rmadim. Shu sabab bu versiya frontendga mos bo'lish ehtimolini oshirish uchun maksimal moslashuvchan qilib yozildi. Agar frontendning `fetch` yoki `axios` kodini yuborsangiz, keyingi versiyada 1:1 exact moslab berish mumkin.
