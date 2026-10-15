# 🏙️ Smart City Light Monitoring & Drone Maintenance System

Комплексная система мониторинга городского освещения с использованием цифрового двойника города, AI-прогнозирования поломок и автономных дронов для обслуживания инфраструктуры.

![Dashboard Preview](https://via.placeholder.com/800x400?text=Smart+City+Dashboard+Preview)

---

## 🚀 Основные возможности

### 🗺️ Цифровой двойник города (Frontend)
*   **2D и 3D режимы**: Интерактивная карта на базе **Leaflet** (2D) и **MapLibre GL JS** (3D) с отображением зданий и точным расположением фонарей.
*   **Real-time мониторинг**: Статус ламп (🟢 Работает, 🔴 Сломана, 🟡 Требует внимания) обновляется в реальном времени через **WebSocket**.
*   **Детальная телеметрия**: При клике на лампу отображаются напряжение, ток, мощность, температура и вероятность отказа.
*   **Стек**: React, Vite, Tailwind (Glassmorphism UI).

### 🧠 AI Предиктивная аналитика (AI Core)
*   **Прогнозирование сбоев**: ML-модель (**XGBoost**) анализирует скачки напряжения, температурные режимы и возраст лампы, предсказывая вероятность поломки на 7 дней вперед.
*   **Интерактивный дашборд**: Отдельный UI на **Streamlit** для аналитиков данных (матрицы корреляций, feature importance).

### 🚁 Умная маршрутизация дронов (Routing AI)
*   **Оптимизация полетов**: Алгоритм строит маршрут облета сломанных ламп с учетом **заряда батареи**, **грузоподъемности** и **погодных условий** (скорость и направление ветра).
*   **Симуляция**: Визуализация полета дрона от базы (Дронопорт) к точкам обслуживания.

### ⚙️ Backend & IoT
*   **Управление устройствами**: Поддержка протокола **Modbus** (реальные контроллеры) и режима симуляции (Mock).
*   **API**: REST API на **FastAPI** + WebSocket для мгновенных обновлений.
*   **База данных**: Хранение истории инцидентов и телеметрии.

---

## 🛠️ Технологический стек

*   **Frontend**: React, MapLibre GL JS, Leaflet, Vite.
*   **Backend**: Python, FastAPI, SQLModel, WebSocket.
*   **AI/ML**: Scikit-learn, XGBoost, Pandas, Streamlit.
*   **Инфраструктура**: Docker, Docker Compose.

---

## 📦 Установка и запуск

Для запуска проекта потребуется **Python 3.10+** и **Node.js 18+**. Рекомендуется использовать менеджер пакетов `uv` для Python.

### 1. Запуск Backend (API & WebSocket)

```bash
cd backend
# Создание виртуального окружения и установка зависимостей
uv venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate # Linux/macOS

uv pip install -r requirements.txt

# Запуск сервера
python -m app.main
```
*Сервер запустится на `http://localhost:8000`*

### 2. Запуск AI Сервисов

**Predictive Maintenance (Прогнозы поломок):**
```bash
cd AI
uv pip install -r requirements.txt
# Запуск API прогнозов
python main.py 
# (Опционально) Запуск UI дашборда
streamlit run dashboard.py
```
*API: `http://localhost:8001`, Dashboard: `http://localhost:8501`*

**Routing Engine (Маршрутизация дронов):**
```bash
cd Routing-AI
uv pip install -r requirements.txt
python main.py
```
*API: `http://localhost:8002`*

### 3. Запуск Frontend (Веб-интерфейс)

```bash
cd frontend
npm install
npm run dev
```
*Приложение доступно по адресу `http://localhost:5173`*

---

## 📡 Структура API

### Основной Backend (`:8000`)
*   `GET /api/lamps` — Список всех ламп с текущим статусом.
*   `GET /api/lamps/{id}` — Детальная информация о лампе.
*   `WS /ws` — WebSocket для получения обновлений в реальном времени.

### AI Prediction (`:8001`)
*   `POST /predict` — Расчет вероятности отказа на основе переданных параметров (вольтаж, часы работы и т.д.).

### Routing Engine (`:8002`)
*   `POST /api/v1/optimize` — Расчет оптимального маршрута для дрона.

---

## 📂 Структура проекта

```
.
├── AI/                 # ML-модели и скрипты прогнозирования (XGBoost)
├── Routing-AI/         # Сервис оптимизации маршрутов дронов
├── backend/            # Основной API (FastAPI) и логика работы с БД
│   ├── app/
│   │   ├── controller/ # Драйверы (Modbus / Mock)
│   │   ├── models/     # SQLModel схемы
│   │   └── services/   # Логика (Polling, WebSocket)
├── frontend/           # React-приложение
│   ├── src/
│   │   ├── components/ # Компоненты карты (2D/3D)
│   │   └── assets/     # 3D модели и иконки
└── docker-compose.yml  # Оркестрация контейнеров
```

---

## 👥 Команда

Разработано специально для хакатона **IT-Tupolev 2026**.
