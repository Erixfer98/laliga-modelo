import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const baseURL = process.env.CAPTURAS_URL || "http://127.0.0.1:3100";
const output = process.env.CAPTURAS_DIR || "../docs/fase4/capturas";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
    : {}),
});
try {
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 1440, height: 1000 },
  ]) {
    for (const colorScheme of ["light", "dark"]) {
      const context = await browser.newContext({
        viewport,
        colorScheme,
        reducedMotion: "reduce",
        isMobile: viewport.width === 390,
        hasTouch: viewport.width === 390,
      });
      if (process.env.CAPTURAS_CLAVE)
        await context.request.post(`${baseURL}/api/entrar`, {
          form: { clave: process.env.CAPTURAS_CLAVE },
        });
      const page = await context.newPage();
      await page.goto(baseURL);
      await page
        .getByText("Último partido registrado:", { exact: false })
        .waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({
        path: `${output}/despues-inicio-${viewport.width}-${colorScheme}.png`,
        fullPage: true,
      });
      await page.goto(`${baseURL}/partido`);
      await page.getByTestId("probabilidad-seleccionada").waitFor();
      await page.screenshot({
        path: `${output}/despues-analisis-${viewport.width}-${colorScheme}.png`,
        fullPage: true,
      });
      // Entrada manual de prueba: no es una cuota de una casa de apuestas.
      await page.getByLabel("Tu cuota decimal").fill("1.90");
      await page
        .getByRole("button", { name: "Añadir al boleto", exact: true })
        .click();
      await page.goto(`${baseURL}/boleto`);
      await page.getByTestId("probabilidad-conjunta").waitFor();
      await page.screenshot({
        path: `${output}/despues-boleto-${viewport.width}-${colorScheme}.png`,
        fullPage: true,
      });
      console.log(`${viewport.width}: ${colorScheme}`);
      await context.close();
    }
  }
} finally {
  await browser.close();
}
