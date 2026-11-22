# قراردادهای API

قراردادها در `apps/web/types` تثبیت شده‌اند تا mock→live بدون بازنویسی UI انجام شود.

## Run
- `POST /api/runs` → `{ run_id }`
- `GET /api/runs/{id}` → snapshot (run, events, markets, buyers, feasibility?, report?)
- `GET /api/runs/{id}/events` — SSE (فاز B)
- `GET /api/runs/{id}/markets`
- `POST /api/runs/{id}/buyers`
- `POST /api/runs/{id}/feasibility`
- `GET /api/runs/{id}/report`

## Admin
- `/api/admin/providers`, `/model`, `/usage`, `/test-connection` — فقط پس از احراز هویت (فاز B)

## رویداد استاندارد
`event_id`, `run_id`, `phase`, `status`, `message_fa`, `timestamp`, `payload?`, `source_refs?`, `error_code?`

## انواع اصلی
`Source`, `Market`, `Buyer`, `Feasibility`, `Run` — جزئیات در `apps/web/types/index.ts`
