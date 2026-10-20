import { test, expect } from "@playwright/test";

// Resumen de la liga (antes era Inicio).
const api = "http://127.0.0.1:8000";
test.beforeEach(async ({ page }) => {
  await page.request.post("/api/entrar", {
    form: { clave: "kuota-e2e-access" },
  });
});

test("Pulso: cinco equipos en móvil, lista completa en escritorio y filtros conservados", async ({
  page,
  request,
}, info) => {
  await page.goto("/liga");
  await expect(
    page.getByText("Último partido registrado:", { exact: false }),
  ).toBeVisible();
  const data = await (
    await request.get(`${api}/liga/laliga`, {
      params: { tendencias: "corners" },
    })
  ).json();
  const rows = page.locator(
    '#pulso-equipos [data-testid="equipo-pulso"]:visible',
  );
  const expand = page.getByRole("button", {
    name: `Ver los ${data.tendencias.filas.length} equipos`,
    exact: true,
  });
  await expect(rows).toHaveCount(
    info.project.name === "iphone" ? 5 : data.tendencias.filas.length,
  );
  if (info.project.name === "desktop") {
    await expect(expand).not.toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(rows).toHaveCount(5);
  }
  for (let i = 0; i < 5; i++)
    await expect(rows.nth(i)).toContainText(data.tendencias.filas[i].equipo);
  await expect(expand).toHaveAttribute("aria-controls", "pulso-equipos");
  await expect(expand).toHaveAttribute("aria-expanded", "false");
  await expand.click();
  await expect(rows).toHaveCount(data.tendencias.filas.length);
  const collapse = page.getByRole("button", {
    name: "Mostrar solo cinco equipos",
    exact: true,
  });
  await expect(collapse).toHaveAttribute("aria-expanded", "true");
  const filters = page.getByRole("group", {
    name: "Métrica de tendencias",
    exact: true,
  });
  await filters.getByRole("button", { name: "Goles", exact: true }).click();
  const goals = await (
    await request.get(`${api}/liga/laliga`, { params: { tendencias: "goles" } })
  ).json();
  await expect(rows).toHaveCount(goals.tendencias.filas.length);
  await expect(
    filters.getByRole("button", { name: "Goles", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await collapse.click();
  await expect(rows).toHaveCount(5);
  await expect(
    filters.getByRole("button", { name: "Goles", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(rows).toHaveCount(goals.tendencias.filas.length);
  await expect(collapse).not.toBeVisible();
});
