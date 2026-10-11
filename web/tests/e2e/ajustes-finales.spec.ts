import { test, expect, type Page } from "@playwright/test";

const api = "http://127.0.0.1:8000";
test.beforeEach(async ({ page }) => {
  await page.request.post("/api/entrar", {
    form: { clave: "kuota-e2e-access" },
  });
});
async function analizar(page: Page) {
  await page.goto("/partido");
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
}
async function agregar(page: Page) {
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await page
    .getByRole("button", { name: "Añadir al boleto", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ya está en tu boleto" }),
  ).toBeDisabled();
}

test("Pulso: cinco equipos en móvil, lista completa en escritorio y filtros conservados", async ({
  page,
  request,
}, info) => {
  await page.goto("/");
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

test("historial de mercados identifica ambos equipos y distingue partido de partidos", async ({
  page,
  request,
}) => {
  await analizar(page);
  const local = await page
    .getByLabel("Equipo local", { exact: true })
    .inputValue();
  const visitante = await page
    .getByLabel("Equipo visitante", { exact: true })
    .inputValue();
  const data = await (
    await request.get(`${api}/liga/laliga/partido`, {
      params: { local, visitante },
    })
  ).json();
  const marketRows = page
    .getByRole("group", { name: "Seleccionar mercado", exact: true })
    .getByRole("button");
  const group = data.mercados.find(
    (m: { mercado: string }) => m.mercado === data.pata.mercado,
  ).grupo;
  const markets = data.mercados.filter(
    (m: { grupo: string }) => m.grupo === group,
  );
  await expect(marketRows).toHaveCount(markets.length);
  for (let i = 0; i < markets.length; i++) {
    const m = markets[i];
    const history = marketRows.nth(i).getByTestId("historico-mercado");
    await expect(history).toContainText(
      `${local}: ${m.hl} de ${m.nl} ${m.nl === 1 ? "partido" : "partidos"}`,
    );
    await expect(history).toContainText(
      `${visitante}: ${m.hv} de ${m.nv} ${m.nv === 1 ? "partido" : "partidos"}`,
    );
  }
  // Respuesta aislada de prueba: muestras de tamaño uno para verificar concordancia.
  await page.route("**/liga/laliga/partido?**", async (route) => {
    const response = await route.fetch();
    const v = await response.json();
    for (const m of v.mercados ?? [])
      Object.assign(m, { hl: 1, nl: 1, hv: 0, nv: 1 });
    if (v.pata) Object.assign(v.pata, { hl: 1, nl: 1, hv: 0, nv: 1 });
    if (new URL(route.request().url()).searchParams.get("modo") === "detalle")
      Object.assign(v, { hl: 1, nl: 1, hv: 0, nv: 1 });
    await route.fulfill({ response, json: v });
  });
  await page.reload();
  await expect(page.getByTestId("historico-mercado").first()).toContainText(
    `${local}: 1 de 1 partido`,
  );
  await expect(page.getByTestId("historico-mercado").first()).not.toContainText(
    "1 partidos",
  );
  await page.getByText("Histórico y sensibilidad", { exact: false }).click();
  await expect(page.locator("#seleccion")).toContainText(
    `${visitante}: 0 de 1 partido`,
  );
});

test("Inicio y Boleto usan selección en singular y selecciones en plural", async ({
  page,
}) => {
  await analizar(page);
  await agregar(page);
  await page.goto("/boleto");
  await expect(
    page.getByText("1 selección · boleto guardado en este dispositivo", {
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/");
  await expect(
    page.getByText("selección guardada", { exact: true }),
  ).toBeVisible();
  await analizar(page);
  await page
    .getByRole("group", { name: "Seleccionar mercado", exact: true })
    .getByRole("button")
    .nth(1)
    .click();
  await expect(page.getByLabel("Tu cuota decimal")).toHaveValue("");
  await agregar(page);
  await page.goto("/boleto");
  await expect(
    page.getByText("2 selecciones · boleto guardado en este dispositivo", {
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/");
  await expect(
    page.getByText("selecciones guardadas", { exact: true }),
  ).toBeVisible();
});
