import { expect, test } from "@playwright/test";

/**
 * Reproducible smoke: Persian RTL home → start analysis → analysis cockpit URL.
 * Default target: local FastAPI (PROVIDER_MODE=stub) via NEXT_PUBLIC_DATA_SOURCE=live.
 * Fixture path: E2E_DATA_SOURCE=mock (Next mock adapter — no API required).
 */
test.describe("NOVA Persian home smoke", () => {
  test("loads RTL home and starts an analysis", async ({ page }) => {
    await page.goto("/");

    await expect(page.locator("html")).toHaveAttribute("lang", "fa");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

    // Brand + Persian hero copy
    await expect(page.getByText("NOVA", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("هوش صادراتی").first()).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "بازار صادراتی را با شواهد پیدا کنید" })
    ).toBeVisible();

    const product = page.locator("#product");
    await expect(product).toBeVisible();
    await product.fill("پسته خام");

    const origin = page.locator("#origin");
    await expect(origin).toBeVisible();
    await origin.fill("ایران");

    await page.getByRole("button", { name: "شروع تحلیل صادرات" }).click();

    // Navigates to analysis cockpit for the new run
    await expect(page).toHaveURL(/\/analysis\/[^/?#]+/, { timeout: 60_000 });

    // Cockpit chrome — Persian labels, no need for markets to finish
    await expect(page.getByText("میز فرمان هوشمند").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText("مسیر تحقیق").first()).toBeVisible();
  });
});
