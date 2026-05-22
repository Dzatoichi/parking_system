# Changelog

## [Спринт №1] 17.04.2026 - 01.05.2026


# 17.04
## Рефактор кода в parking-managment-service.
Привёл parking-management-service к более цельной слоистой схеме(router, service, DAO). Основной рефактор ушёл в слой бронирований: переписаны booking_service.py, booking_dao.py, booking_schemas.py и booking_router.py. Заодно исправил конфиг в config.py, чтобы сервис и тесты не падали на импорте, добавил миграцию для таблицы бронирований.

# 18.04
## Написание сервиса аутентификации и добавление hot-reload контейнеров.
### Hot-reload
-docker-compose.yml перевёл на dev-схему: bind mounts для исходников, WATCHFILES_FORCE_POLLING=true для Python-сервисов, CHOKIDAR_USEPOLLING=true для фронтенда, healthcheck'и для cv-processing-service и stream-ingest-service, фронтенд теперь слушает 3000:3000.
-backend/parking-management-service/Dockerfile, backend/cv-processing-service/Dockerfile, backend/stream-ingest-service/Dockerfile теперь ставят watchfiles и запускают uvicorn ... --reload.
-frontend/src/Dockerfile и frontend/Dockerfile перевёл с production/nginx-запуска на vite dev внутри контейнера.
-В frontend/src/vite.config.ts добавил host: '0.0.0.0', отключил open, и прокси теперь берёт target из VITE_API_PROXY_TARGET, чтобы внутри Docker фронтенд ходил в parking-management-service, а локально мог остаться на localhost.

### Auth-service
-Написал базовую структуру auth-service:
Создал ORM модель пользователя с ролями и его правами доступа.
-Написаны роутеры аунтентификации и пользовательский роутер.
-Реализована JWT/stateful-token архитектура: access, refresh, registration invite token и reset token.
-Добавлены зависимости poetry.
-Написаны pydantic-схемы.
-Внедрение зависимостей через файл src/utils/dependencies.py.
-Dockerfile и добавление в docker-compose.yml

# 24.05
## Рефакторинг frontend приложения
-Фронт отрефакторен в более чистую структуру без изменения пользовательского поведения. Навигация и shell вынесены из App.tsx в app/AppShell.tsx, app/screens.tsx и app/queryClient.ts. QueryClientProvider перенесен в main.tsx, а Sidebar больше не зависит от App.
-Page-level запросы и polling вынесены из компонентов в hooks:useActiveParking.ts, useDashboardData.ts, useAnalyticsOverview.ts, useParkingMapData.ts, useVehicleSearchData.ts. Из-за этого Dashboard.tsx, Analytics.tsx, ParkingMap.tsx и VehicleSearch.tsx стали существенно чище: в них остался в основном UI, а не orchestration запросов. Общий разбор API-ошибок вынесен в lib/api.ts. Старый неиспользуемый hook useParkingStats.ts удален.


# 26.05 
## Рефактор
-Удаление лишних коммитов в бд в parking-manegment-sevice.
-Добавление middleware в auth-service.
-Добавление поля owner_id в моделе vehicle_table, последующая миграция.
-Добавил авторизацию и аутентификацию на клиентскую часть.

# 29.05
## Добавление device-service
-Реализован функционал управления внешними системами(свет, шлагбаум), с помощью 4 эндпоинтов.
-Добавление интерфейса на клиентскую часть.
