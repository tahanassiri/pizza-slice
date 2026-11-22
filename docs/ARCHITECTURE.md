# معماری NOVA Export Intelligence

## فاز فعلی
فاز A: فرانت‌اند مستقل با adapter آزمایشی. بک‌اند FastAPI، SSE واقعی و providerها در فاز B+.

## مرزها
- `apps/web` — Next.js UI، RTL فارسی، قراردادهای نوع‌دار
- `lib/api` — کلاینت واحد؛ `mock-adapter` امروز، `live` بعداً بدون بازنویسی صفحات
- `apps/api` — هنوز پیاده نشده (فاز B)
- کلید API فقط سمت سرور در فازهای بعد؛ در مرورگر ذخیره نمی‌شود

## جریان داده (فاز A)
`ProductInput` → `api.createRun` (mock) → `RunSnapshot` در حافظه مرورگر → صفحات analysis / report / admin UI

## به‌روزرسانی زنده
در فاز A تایم‌لاین از fixture و با برچسب «پیش‌نمایش آزمایشی» است. SSE واقعی متعلق به فاز B است.
