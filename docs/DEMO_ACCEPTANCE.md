# معیار پذیرش دمو

معیارهای محصول نهایی (فاز D) در بلوپرینت آمده‌اند. برای **فاز A** حداقل این‌ها باید برقرار باشند:

- [ ] تمام routeها قابل پیمایش: `/`, `/analysis/[id]` (+ تب‌ها), `/admin/login`, `/admin`
- [ ] RTL و فارسی یکدست
- [ ] داده آزمایشی با برچسب «داده آزمایشی» / «پیش‌نمایش آزمایشی»
- [ ] fixtureها قابل انتخاب: happy, sparse, unavailable, quota, partial, incomplete_financial
- [ ] بدون درخواست واقعی به Tavily/Exa/Gemini/Comtrade
- [ ] بدون ذخیره کلید API در مرورگر
- [ ] lint / typecheck / build سالم
- [ ] گزارش چاپ‌پذیر در `/analysis/[id]` تب report
