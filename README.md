# NOVA Export Intelligence

فاز A: فرانت‌اند فارسی/RTL با داده آزمایشی.

## اجرای محلی

```bash
cd apps/web
npm install
npm run dev
```

باز کردن: [http://localhost:3000](http://localhost:3000)

## اسکریپت‌ها

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## یادداشت‌ها

- منبع داده پیش‌فرض: mock (`NEXT_PUBLIC_DATA_SOURCE=mock`)
- کلید API در مرورگر ذخیره نمی‌شود
- Graphify MCP در محیط ساخت این نسخه در دسترس نبود
- مخزن محلی است؛ بدون مجوز کاربر به سرویس ثالث پوش نشود

## مسیرها

| مسیر | توضیح |
|------|--------|
| `/` | شروع تحلیل |
| `/analysis/[id]` | تایم‌لاین و تب‌های نتیجه |
| `/admin/login` | ورود نمایشی مدیر |
| `/admin` | تنظیمات نمایشی |
