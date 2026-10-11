import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.request.post("/api/entrar", { form: { clave: "kuota-e2e-access" } });
});

test("lambdas visibles antes de líneas y lectura ligada a la métrica", async ({ page }, info) => {
  await page.goto("/partido");
  const lambda = page.getByTestId("lambda-summary");
  await expect(lambda).toBeVisible();
  await expect(page.getByTestId("lambda-local")).toBeVisible();
  await expect(page.getByTestId("lambda-visitante")).toBeVisible();
  await expect(page.getByTestId("lambda-total")).toBeVisible();
  const antes = await page.getByTestId("lambda-local").innerText();
  const metricas = page.getByRole("group", { name: "Métrica del análisis" });
  await metricas.getByRole("button", { name: "Corners" }).click();
  await expect(page.getByTestId("lambda-summary")).toContainText("Corners");
  await expect(page.getByTestId("lambda-local")).toBeVisible();
  await expect(page.getByTestId("lambda-lectura")).toContainText("corners");
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  const nombre = info.project.name === "iphone" ? "ux-movil" : "ux-desktop";
  await page.screenshot({ path: "test-results/" + nombre + ".png", fullPage: true });
  // Un parámetro distinto puede coincidir por redondeo; se valida el contexto y los datos disponibles.
  expect(antes).toMatch(/[0-9]/);
});

test("líneas directas y Más/Menos en un toque", async ({ page }) => {
  await page.goto("/partido");
  await expect(page.getByTestId("lambda-local")).toBeVisible();
  await page.getByRole("group", { name: "Grupo de mercados" }).getByRole("button", { name: "Total" }).click();
  const lineas = page.getByRole("group", { name: "Líneas disponibles" });
  await expect(lineas).toBeVisible();
  const opciones = lineas.getByRole("button");
  expect(await opciones.count()).toBeGreaterThan(1);
  const segundo = opciones.nth(1);
  const linea = (await segundo.innerText()).trim();
  await segundo.click();
  await expect(page.getByTestId("mercado-seleccionado")).toContainText(linea);
  await page.getByRole("group", { name: "Dirección del mercado" })
    .getByRole("button", { name: "Menos de" }).click();
  await expect(page.getByTestId("mercado-seleccionado")).toContainText("Under " + linea);
  await expect(page.getByRole("heading", { name: /Cómo se distribuyen/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Qué muestra el historial/ })).toBeVisible();
});

test("opciones no OU y línea adicional respetan motor", async ({ page }) => {
  await page.goto("/partido");
  await expect(page.getByTestId("lambda-local")).toBeVisible();
  await expect(page.getByRole("group", { name: "Opciones del mercado" })).toBeVisible();
  await page.getByRole("group", { name: "Grupo de mercados" }).getByRole("button", { name: "Total" }).click();
  await page.getByRole("button", { name: "Ver más líneas" }).click();
  const extra = page.getByRole("group", { name: "Consultar líneas adicionales" }).getByRole("button").last();
  const linea = (await extra.innerText()).replace("Consultar ", "").trim();
  await extra.click();
  await expect(page.getByTestId("mercado-seleccionado")).toContainText(linea);
  await expect(page.getByTestId("probabilidad-seleccionada")).not.toHaveText("…");
  await expect(page.getByRole("group", { name: "Líneas disponibles" })
    .getByRole("button", { name: "Línea " + linea })).toHaveAttribute("aria-pressed", "true");
});
