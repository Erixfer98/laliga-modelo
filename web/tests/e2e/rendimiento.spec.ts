import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.request.post("/api/entrar", {
    form: { clave: "kuota-e2e-access" },
  });
});
async function iniciar(page: import("@playwright/test").Page) {
  await page.goto("/partido");
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  await page.getByText("Ver lista completa de mercados", { exact: true }).click();
}
test("mercados y grupos actualizan sin solicitar de nuevo el análisis base", async ({
  page,
}) => {
  const solicitudes: string[] = [];
  page.on("request", (r) => {
    if (/\/liga\/[^/]+\/partido\?/.test(r.url())) solicitudes.push(r.url());
  });
  await iniciar(page);
  let liberar!: () => void;
  const detallePendiente = new Promise<void>((resolve) => {
    liberar = resolve;
  });
  await page.route("**/partido?**", async (route) => {
    if (new URL(route.request().url()).searchParams.get("modo") === "detalle")
      await detallePendiente;
    await route.continue();
  });
  const inicial = solicitudes.filter(
    (u) => new URL(u).searchParams.get("modo") === "resumen",
  ).length;
  const mercados = page.getByRole("group", {
    name: "Seleccionar mercado",
    exact: true,
  });
  const segundo = mercados.getByRole("button").nth(1);
  await segundo.click();
  await expect(segundo).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  await page.getByLabel("Tu cuota decimal").fill("1.9");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeDisabled();
  const grupos = page.getByRole("group", {
    name: "Grupo de mercados",
    exact: true,
  });
  await grupos.getByRole("button", { name: "Total", exact: true }).click();
  await expect(mercados.getByRole("button").first()).toContainText("Total");
  for (let i = 0; i < 5; i++)
    await mercados
      .getByRole("button")
      .nth(i % 3)
      .click();
  await expect(mercados.getByRole("button").nth(1)).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByLabel("Tu cuota decimal")).toHaveValue("");
  await expect
    .poll(
      () =>
        solicitudes.filter(
          (u) => new URL(u).searchParams.get("modo") === "resumen",
        ).length,
    )
    .toBe(inicial);
  expect(
    solicitudes.filter(
      (u) =>
        !["resumen", "detalle"].includes(
          new URL(u).searchParams.get("modo") || "",
        ),
    ),
  ).toHaveLength(0);
  liberar();
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Añadir al boleto", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ya está en tu boleto" }),
  ).toBeDisabled();
  const stored = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("kuota-v1")!),
  );
  expect(stored.boleto[0].mercado).toContain("Total");
  await page.reload();
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  await page.goto("/boleto");
  await expect(page.getByTestId("probabilidad-conjunta")).toBeVisible();
});
test("líneas consecutivas conservan el último ajuste y bloquean el boleto mientras se verifican", async ({
  page,
}) => {
  const solicitudes: string[] = [];
  page.on("request", (r) => {
    if (
      /\/liga\/[^/]+\/partido\?/.test(r.url()) &&
      new URL(r.url()).searchParams.get("modo") === "resumen"
    )
      solicitudes.push(r.url());
  });
  await iniciar(page);
  await page
    .getByRole("group", { name: "Grupo de mercados", exact: true })
    .getByRole("button", { name: "Total", exact: true })
    .click();
  await page.getByText("Ajustar líneas e historial", { exact: false }).click();
  const rows = page.getByRole("group", {
    name: "Seleccionar mercado",
    exact: true,
  });
  const primerNombre = await rows.getByRole("button").first().innerText();
  await page.route("**/partido?**", async (route) => {
    if (new URL(route.request().url()).searchParams.get("modo") === "resumen")
      await new Promise((r) => setTimeout(r, 450));
    await route.continue();
  });
  await page.getByLabel("Aumentar línea", { exact: true }).click();
  await page.getByLabel("Aumentar línea", { exact: true }).click();
  await page.getByLabel("Reducir línea", { exact: true }).click();
  await expect(page.getByTestId("probabilidad-seleccionada")).toHaveText("…");
  await expect(rows.getByRole("button").first()).not.toHaveText(primerNombre);
  const local = await page
      .getByLabel("Equipo local", { exact: true })
      .inputValue(),
    visitante = await page
      .getByLabel("Equipo visitante", { exact: true })
      .inputValue();
  await expect(page.getByTestId("probabilidad-seleccionada")).not.toHaveText(
    "…",
  );
  const url = new URL(solicitudes.at(-1)!);
  url.searchParams.set("modo", "completo");
  url.searchParams.set("grupo", "Total");
  url.searchParams.set(
    "pata",
    (await page.getByTestId("mercado-seleccionado").innerText()).trim(),
  );
  const response = await page.request.get(url.toString());
  const vista = await response.json();
  const detalle = vista.pata;
  await expect(page.getByTestId("probabilidad-seleccionada")).toHaveText(
    `${(detalle.prob * 100).toFixed(1)}%`,
  );
  expect(detalle.seleccion.local).toBe(local);
  expect(detalle.seleccion.visitante).toBe(visitante);
  // No perder un ajuste de otro grupo mientras su solicitud está pendiente.
  await page.getByLabel("Aumentar línea", { exact: true }).click();
  await page
    .getByRole("group", { name: "Grupo de mercados", exact: true })
    .getByRole("button", { name: local, exact: true })
    .click();
  await page.getByLabel("Aumentar línea", { exact: true }).click();
  await expect(page.getByTestId("probabilidad-seleccionada")).not.toHaveText(
    "…",
  );
  const finalCfg = JSON.parse(
    new URL(solicitudes.at(-1)!).searchParams.get("cfg")!,
  );
  expect(finalCfg.Total[0]).toBe(vista.cfg.Total[0] + 1);
  expect(finalCfg[local][0]).toBe(vista.cfg[local][0] + 1);
});
test("cambio de equipos pendiente y versión rechazada no permite añadir datos anteriores", async ({
  page,
}) => {
  await iniciar(page);
  await page.route("**/partido?**", async (route) => {
    const u = new URL(route.request().url());
    if (u.searchParams.get("modo") === "detalle") {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Los datos cambiaron; actualiza el análisis",
        }),
      });
    } else await route.continue();
  });
  await page
    .getByRole("group", { name: "Seleccionar mercado", exact: true })
    .getByRole("button")
    .nth(1)
    .click();
  await expect(
    page.getByText(
      "Los datos o el modelo cambiaron. Actualiza el análisis antes de añadir al boleto.",
    ),
  ).toBeVisible();
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeDisabled();
  await page.unroute("**/partido?**");
  await page.route("**/partido?**", async (route) => {
    await new Promise((r) => setTimeout(r, 400));
    await route.continue();
  });
  await page
    .getByLabel("Equipo local", { exact: true })
    .selectOption("Barcelona");
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Añadir al boleto", exact: true })
    .click();
  await page
    .getByLabel("Equipo local", { exact: true })
    .selectOption("Athletic Club");
  await expect(
    page.getByRole("heading", { name: /Athletic Club vs/ }),
  ).toBeVisible();
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Añadir al boleto", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ya está en tu boleto" }),
  ).toBeDisabled();
  const s = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("kuota-v1")!),
  );
  expect(s.boleto).toHaveLength(1);
  expect(s.boleto[0].seleccion.local).toBe("Athletic Club");
});

test("una versión cambiada al pulsar añadir se rechaza sin guardar la selección", async ({
  page,
}) => {
  await iniciar(page);
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeEnabled();
  await page.route("**/liga/laliga/partido?**", async (route) => {
    if (new URL(route.request().url()).searchParams.get("modo") === "version")
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Los datos cambiaron antes de añadir" }),
      });
    else await route.continue();
  });
  await page
    .getByRole("button", { name: "Añadir al boleto", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () => JSON.parse(localStorage.getItem("kuota-v1")!).boleto.length,
      ),
    )
    .toBe(0);
  await expect(
    page.getByText(
      "El análisis cambió antes de añadir. Actualiza los datos e inténtalo de nuevo.",
    ),
  ).toBeVisible();
});
