# Схема базы данных — Smart Streetlight System

## ER-диаграмма

```
┌──────────────────────────────┐
│        streetlights          │
├──────────────────────────────┤
│ PK  id            int        │
│     name          str        │
│     latitude      float      │
│     longitude     float      │
│     address       str        │
│     modbus_slave_id int (UQ) │
│     installed_at  datetime   │
│     is_active     bool       │
└──────────────┬───────────────┘
               │ 1
               │
               │ 1
┌──────────────┴───────────────┐
│           lamps              │
├──────────────────────────────┤
│ PK  id               int    │
│ FK  streetlight_id   int(UQ)│───► streetlights.id
│     status           enum   │     (ok, burned_out,
│     is_on            bool   │      absent, maintenance)
│ ─── показатели ─────────── │
│     hours_active     int    │  наработка (ч)
│     junction_temp_avg float │  температура перехода (°C)
│     voltage_spike_count int │  скачки напряжения
│     on_off_cycles    int    │  циклы вкл/выкл
│     humidity_avg     float  │  влажность (%)
│     voltage          float  │  напряжение (В)
│     current_ma       float  │  ток (мА)
│     power_w          float  │  мощность (Вт)
│     ambient_temp     float  │  температура среды (°C)
│     reflector_position int  │  позиция отражателя (°)
│ ─── мета ──────────────── │
│     last_seen        datetime│
│     updated_at       datetime│
└──────┬──────────┬────────────┘
       │ 1        │ 1
       │          │
       │ *        │ *
┌──────┴───────┐  │  ┌────────────────────────────┐
│  lamp_events │  │  │     replacement_jobs        │
├──────────────┤  │  ├────────────────────────────┤
│PK id     int │  │  │ PK  id            int      │
│FK lamp_id int│  │  │ FK  lamp_id       int      │───► lamps.id
│  event_type  │  │  │ FK  drone_id      int|null │───► drones.id
│    str       │  │  │     status        enum     │
│  details     │  │  │      (pending, assigned,   │
│    str|null  │  │  │       in_progress,         │
│  created_at  │  │  │       completed, failed)   │
│    datetime  │  │  │     priority      int      │
└──────────────┘  │  │     created_at    datetime  │
                  │  │     assigned_at   dt|null   │
                  │  │     started_at    dt|null   │
                  │  │     completed_at  dt|null   │
                  │  │     failure_reason str|null │
                  │  └─────────────┬──────────────┘
                  │                │ *
                  │                │
                  │                │ 1
                  │  ┌─────────────┴──────────────┐
                  │  │          drones             │
                  │  ├────────────────────────────┤
                  │  │ PK  id              int    │
                  │  │     name            str    │
                  │  │     model           str    │
                  │  │     status          enum   │
                  │  │      (idle, in_flight,     │
                  │  │       charging,            │
                  │  │       maintenance, offline)│
                  │  │     battery_level   float  │
                  │  │     latitude        float  │
                  │  │     longitude       float  │
                  │  │     total_flights   int    │
                  │  │     total_replacements int │
                  │  │     last_maintenance dt    │
                  │  │     created_at      datetime│
                  │  └────────────────────────────┘

```

## Связи

```
streetlights  1 ─── 1  lamps              Один столб = одна лампа
lamps         1 ─── *  replacement_jobs    У лампы может быть история замен
drones        1 ─── *  replacement_jobs    Дрон выполняет много заданий
lamps         1 ─── *  lamp_events         История событий лампы
```

## Enum-значения

| Enum | Значения |
|------|----------|
| LampStatus | `ok`, `burned_out`, `absent`, `maintenance` |
| DroneStatus | `idle`, `in_flight`, `charging`, `maintenance`, `offline` |
| JobStatus | `pending`, `assigned`, `in_progress`, `completed`, `failed` |

## Файлы
- `app/models.py` — SQLModel-модели
- `app/database.py` — подключение SQLite
- БД создаётся автоматически: `lamps.db`
