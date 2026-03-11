# Архитектура проекта booking-core

## Структура файлов и папок

```
booking-core/
│
├── config.py                    # Настройки приложения (чтение .env)
├── database.py                  # Подключение к SQLite, сессии SQLAlchemy
├── utils.py                     # Общие вспомогательные функции
├── main.py                      # Точка входа, инициализация FastAPI
├── .env                         # Переменные окружения (исключен из git)
├── requirements.txt             # Зависимости проекта
├── README.md                    # Документация по запуску и разработке
│
├── hotels/                       # Домен: Отели и номера
│   ├── models.py                 # Модели Hotel, Room, RoomRule
│   ├── schemas.py                # Pydantic схемы для отелей и номеров
│   ├── hotels.py                 # Бизнес-логика домена hotels
│   └── routes.py                 # API эндпоинты: /hotels, /hotels/{id}/rooms
│

├── bookings/                      # Домен: Бронирования
│   ├── models.py                  # Модель Booking
│   ├── schemas.py                 # Схемы для создания и просмотра броней
│   ├── bookings.py                # Бизнес-логика домена bookings
│   └── routes.py                  # API: /booking/calculate, /booking/create, /booking/{id}
│
├── stock/                         # Домен: Наличие свободных номеров
│   ├── models.py                  # Модель занятости по датам
│   ├── schemas.py                 # Схемы для календаря и проверки дат
│   ├── stock.py                   # Бизнес-логика домена stock
│   └── routes.py                  # API: /rooms/{id}/availability
│
├── bitrix/                        # Домен: Интеграция с Битрикс24
│   └── bitrix.py                  # Клиент для работы с REST API Битрикса
│
├── captcha/                       # Домен: Защита от ботов
│   └── captcha.py                 # Проверка токена Яндекс.Капчи
│
├── admin/                         # Домен: Административная панель
│   ├── auth.py                    # Авторизация в админке
│   ├── admin.py                   # Основная логика админки
│   ├── routes.py                  # Все роуты административной панели
│   ├── templates/                  # HTML шаблоны (Jinja2)
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── hotels/
│   │   │   ├── list.html
│   │   │   ├── create.html
│   │   │   └── edit.html
│   │   ├── rooms/
│   │   │   ├── list.html
│   │   │   └── edit.html
│   │   ├── bookings/
│   │   │   ├── list.html
│   │   │   └── detail.html
│   │   └── settings/
│   │       └── status_mapping.html
│   └── static/                     # Статические файлы (CSS, JS)
│       ├── css/
│       │   └── admin.css
│       └── js/
│           └── admin.js
│
└── data/                           # Файловое хранилище
    ├── bookings.db                 # Файл базы данных SQLite
    └── uploads/                     # Загруженные файлы (фото номеров, иконки)
```

## Описание доменов

| Домен | Назначение | Ключевые файлы |
|-------|------------|----------------|
| **hotels** | Управление отелями и номерами | `models.py`, `schemas.py`, `hotels.py`, `routes.py` |
| **bookings** | Создание и управление бронями | `models.py`, `schemas.py`, `bookings.py`, `routes.py` |
| **stock** | Проверка наличия свободных номеров | `models.py`, `schemas.py`, `stock.py`, `routes.py` |
| **bitrix** | Интеграция с CRM Битрикс24 | `bitrix.py` |
| **captcha** | Защита от ботов (Яндекс.Капча) | `captcha.py` |
| **admin** | Административная панель | `auth.py`, `admin.py`, `routes.py`, `templates/`, `static/` |

## Назначение корневых файлов

| Файл | Назначение |
|------|------------|
| `config.py` | Загрузка настроек из `.env`, конфигурация приложения |
| `database.py` | Настройка подключения к SQLite, создание сессий |
| `utils.py` | Общие функции (работа с датами, форматирование) |
| `main.py` | Сборка приложения, подключение роутов, запуск |
| `.env` | Переменные окружения (ключи API, настройки) |
| `requirements.txt` | Список зависимостей Python |
| `README.md` | Документация по установке и запуску |

## Основные принципы архитектуры

1. **Доменная структура** — каждый домен (hotels, bookings, stock) живет в своей папке
2. **Изоляция логики** — бизнес-логика в файлах `hotels.py`, `bookings.py`, `stock.py`
3. **Тонкие роуты** — в `routes.py` только вызовы методов и возврат ответов
4. **Интеграции как домены** — bitrix и captcha выделены в отдельные папки
5. **Админка отдельно** — не смешивается с API,有自己的 шаблоны и статику
