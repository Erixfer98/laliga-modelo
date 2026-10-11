import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const api = "http://127.0.0.1:8000";
const runtimeErrors = new WeakMap<Page, string[]>();
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
test.beforeEach(async ({ page }) => {
  await page.request.post("/api/entrar", {
    form: { clave: "kuota-e2e-access" },
  });
  // Fallos de ejecución son regresiones; errores de recursos externos no se sustituyen.
  const errors: string[] = [];
  runtimeErrors.set(page, errors);
  page.on("pageerror", (e) => errors.push(e.message));
});
test.afterEach(async ({ page }) => {
  expect(
    runtimeErrors.get(page) ?? [],
    "Errores de JavaScript en la página",
  ).toEqual([]);
});
test("autenticación existente: puerta, contraseña incorrecta, entrada y salida", async ({
  browser,
}) => {
  const c = await browser.newContext();
  const p = await c.newPage();
  await p.goto("http://127.0.0.1:3100");
  await expect(p.getByLabel("Contraseña de acceso")).toBeVisible();
  await p.getByLabel("Contraseña de acceso").fill("incorrecta");
  await p.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    p.getByText("Contraseña incorrecta", { exact: true }),
  ).toBeVisible();
  await p.getByLabel("Contraseña de acceso").fill("kuota-e2e-access");
  await p.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    p.getByRole("heading", { name: "El fútbol, con perspectiva." }),
  ).toBeVisible();
  await p.getByLabel("Preferencias").click();
  await p.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(p.getByLabel("Contraseña de acceso")).toBeVisible();
  await c.close();
});
test("navegación y rutas existentes, menú móvil y teclado", async ({
  page,
}, info) => {
  await page.goto("/");
  if (info.project.name === "iphone") {
    const nav = page.getByRole("navigation", { name: "Navegación móvil" });
    await nav.getByRole("button", { name: "Más", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await nav.getByRole("button", { name: "Más", exact: true }).click();
    await page
      .getByRole("dialog")
      .getByRole("link", { name: "Tabla de posiciones" })
      .click();
  } else
    await page
      .getByRole("navigation", { name: "Navegación principal" })
      .getByRole("link", { name: "Tabla", exact: true })
      .click();
  await expect(page).toHaveURL(/\/tabla$/);
  await expect(
    page.getByRole("heading", { name: "Tabla de posiciones." }),
  ).toBeVisible();
  for (const path of ["/cara", "/diccionario", "/boleto", "/partido"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
  }
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Saltar al contenido" }),
  ).toBeFocused();
});
test("cuotas vacías, probabilidades reales, devolución y EV vigentes", async ({
  page,
  request,
}) => {
  await analizar(page);
  await expect(page.getByLabel("Tu cuota decimal")).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeDisabled();
  const local = await page
    .getByLabel("Equipo local", { exact: true })
    .inputValue();
  const visitante = await page
    .getByLabel("Equipo visitante", { exact: true })
    .inputValue();
  const v = await (
    await request.get(`${api}/liga/laliga/partido`, {
      params: { local, visitante },
    })
  ).json();
  await expect(page.getByTestId("probabilidad-seleccionada")).toHaveText(
    `${(v.pata.prob * 100).toFixed(1)}%`,
  );
  await page.getByLabel("Tu cuota decimal").fill("1");
  await expect(
    page.getByRole("button", { name: "Añadir al boleto", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Tu cuota decimal").fill("1.90");
  await expect(
    page
      .getByText(
        (v.pata.prob * 1.9 + v.pata.push - 1 >= 0 ? "+" : "") +
          (v.pata.prob * 1.9 + v.pata.push - 1).toFixed(2),
        { exact: true },
      )
      .first(),
  ).toBeVisible();
  await agregar(page);
  await page.goto("/boleto");
  await expect(page.getByTestId("probabilidad-conjunta")).toBeVisible();
  const stored = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("kuota-v1")!),
  );
  const result = await (
    await request.post(`${api}/boleto`, {
      data: { patas: stored.boleto, banca: stored.banca },
    })
  ).json();
  await expect(page.getByTestId("probabilidad-conjunta")).toHaveText(
    `${(result.resumen.prob * 100).toFixed(1)}%`,
  );
});
test("todas las métricas, grupos, líneas y filtros siguen operativos", async ({
  page,
}) => {
  await analizar(page);
  const metrica = page.getByRole("group", {
    name: "Métrica del análisis",
    exact: true,
  });
  for (const name of [
    "Goles 1T",
    "Goles 2T",
    "Tiros",
    "Tiros a puerta",
    "Corners",
    "Faltas",
    "Amarillas",
    "Rojas",
    "Goles",
  ]) {
    await metrica.getByRole("button", { name, exact: true }).click();
    await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
    await expect(
      metrica.getByRole("button", { name, exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
  }
  const grupos = page.getByRole("group", {
    name: "Grupo de mercados",
    exact: true,
  });
  const names = await grupos.getByRole("button").allTextContents();
  for (const name of names) {
    await grupos.getByRole("button", { name, exact: true }).click();
    await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
  }
  await grupos.getByRole("button", { name: "Total", exact: true }).click();
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
  await page.getByText("Ajustar líneas e historial", { exact: false }).click();
  await page.getByLabel("Número de partidos históricos").selectOption("10");
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
  const summary = page.getByText("Ajustar líneas e historial", {
    exact: false,
  });
  if (!(await page.getByLabel("Aumentar línea").isVisible()))
    await summary.click();
  await page.getByLabel("Aumentar línea").click();
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
  if (!(await page.getByLabel("Líneas alrededor").isVisible()))
    await summary.click();
  await page.getByLabel("Líneas alrededor").selectOption("2");
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
  if (
    !(await page
      .getByRole("switch", { name: "Solo en su condición" })
      .isVisible())
  )
    await summary.click();
  await page.getByRole("switch", { name: "Solo en su condición" }).click();
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
});
test("cambio de equipos y métrica no conserva la cuota de otro mercado", async ({
  page,
}) => {
  await analizar(page);
  await page.getByLabel("Tu cuota decimal").fill("2.10");
  await page
    .getByRole("group", { name: "Métrica del análisis", exact: true })
    .getByRole("button", { name: "Corners", exact: true })
    .click();
  await expect(page.getByLabel("Tu cuota decimal")).toHaveValue("");
  await page
    .getByLabel("Equipo local", { exact: true })
    .selectOption("Barcelona");
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
  await expect(
    page.getByLabel("Equipo visitante", { exact: true }),
  ).not.toHaveValue("Barcelona");
  await page.reload();
  await expect(page.getByLabel("Equipo local", { exact: true })).toHaveValue(
    "Barcelona",
  );
});
test("las respuestas antiguas no aparecen bajo una liga nueva", async ({
  page,
}) => {
  await analizar(page);
  await page.route("**/liga/premier/partido?**", async (route) => {
    await new Promise((r) => setTimeout(r, 1200));
    await route.continue().catch(() => {});
  });
  await page
    .getByRole("group", { name: "Elegir liga" })
    .getByRole("button", { name: "Premier League", exact: true })
    .click();
  await expect(page.getByTestId("probabilidad-seleccionada")).not.toBeVisible();
  await expect(page.getByLabel("Tu cuota decimal")).not.toBeVisible();
  await expect(page.getByTestId("probabilidad-seleccionada")).toBeVisible();
  await expect(
    page
      .getByRole("group", { name: "Elegir liga" })
      .getByRole("button", { name: "Premier League", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});
test("boleto persiste, agrupa y permite quitar; vacío útil", async ({
  page,
}) => {
  await analizar(page);
  await agregar(page);
  await page.goto("/boleto");
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page.reload();
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page.getByRole("button", { name: /^Quitar / }).click();
  await expect(
    page.getByRole("heading", { name: "Tu boleto está vacío" }),
  ).toBeVisible();
});
test("métricas correlacionadas sin modelo y selecciones antiguas no inventan resultado", async ({
  page,
}) => {
  await analizar(page);
  await agregar(page);
  await page
    .getByRole("group", { name: "Métrica del análisis", exact: true })
    .getByRole("button", { name: "Corners", exact: true })
    .click();
  await expect(page.getByLabel("Tu cuota decimal")).toHaveValue("");
  await agregar(page);
  await page.goto("/boleto");
  await expect(
    page.getByRole("heading", { name: "Cálculo conjunto no disponible" }),
  ).toBeVisible();
  await expect(page.getByTestId("probabilidad-conjunta")).not.toBeVisible();
  await expect(
    page
      .getByText("Métricas distintas del mismo partido:", { exact: false })
      .first(),
  ).toBeVisible();
  await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem("kuota-v1")!);
    delete s.boleto[0].seleccion;
    s.boleto = s.boleto.slice(0, 1);
    localStorage.setItem("kuota-v1", JSON.stringify(s));
  });
  await page.reload();
  await expect(
    page
      .getByText("Selección antigua o sin identidad verificable:", {
        exact: false,
      })
      .first(),
  ).toBeVisible();
});
test("errores y reintentos conservan las selecciones", async ({ page }) => {
  await analizar(page);
  await agregar(page);
  await page.route("**/boleto", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 503, body: "offline" })
      : route.continue(),
  );
  await page.goto("/boleto");
  await expect(
    page.getByRole("heading", { name: "No pudimos calcular el boleto" }),
  ).toBeVisible();
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page.unroute("**/boleto");
  await page.getByRole("button", { name: "Reintentar cálculo" }).click();
  await expect(page.getByTestId("probabilidad-conjunta")).toBeVisible();
  await page.route("**/liga/laliga/tabla*", (route) =>
    route.fulfill({ status: 503, body: "offline" }),
  );
  await page.goto("/tabla");
  await expect(
    page.getByRole("heading", { name: "No pudimos cargar los datos" }),
  ).toBeVisible();
  await page.unroute("**/liga/laliga/tabla*");
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(page.getByLabel("Temporada", { exact: true })).toBeVisible();
});
test("glosario, ausencia de resultados y tema persistido", async ({ page }) => {
  await page.goto("/diccionario");
  await page.getByLabel("Buscar en el glosario").fill("zzzz-no-existe");
  await expect(page.getByRole("status")).toContainText("No hay términos");
  await page.getByLabel("Buscar en el glosario").fill("Kelly");
  await expect(
    page.locator("summary").filter({ hasText: "Kelly" }).first(),
  ).toBeVisible();
  await page.getByLabel("Preferencias").click();
  await page
    .getByLabel("Apariencia", { exact: true })
    .first()
    .selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
for (const theme of ["light", "dark"] as const)
  test(`accesibilidad AA y ausencia de overflow: ${theme}`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
    for (const path of [
      "/",
      "/partido",
      "/boleto",
      "/tabla",
      "/cara",
      "/diccionario",
    ]) {
      await page.goto(path);
      if (path === "/partido")
        await expect(
          page.getByTestId("probabilidad-seleccionada"),
        ).toBeVisible();
      else if (path === "/")
        await expect(
          page.getByText("Último partido registrado:", { exact: false }),
        ).toBeVisible();
      else if (path === "/tabla")
        await expect(
          page.getByLabel("Temporada", { exact: true }),
        ).toBeVisible();
      else if (path === "/cara")
        await expect(
          page.getByRole("heading", { name: "Récord directo" }),
        ).toBeVisible();
      else if (path === "/diccionario")
        await expect(
          page.getByRole("heading", { name: "Modelo", exact: true }),
        ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
        path,
      ).toBe(true);
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(
        result.violations,
        `${path}: ${JSON.stringify(result.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })))}`,
      ).toEqual([]);
    }
  });

test("mercados compatibles del mismo partido conservan cálculo conjunto y Kelly", async ({
  page,
  request,
}) => {
  await analizar(page);
  const local = await page
    .getByLabel("Equipo local", { exact: true })
    .inputValue();
  await agregar(page);
  await page
    .getByRole("group", { name: "Seleccionar mercado", exact: true })
    .getByRole("button")
    .filter({ hasText: `${local} o empate` })
    .click();
  await expect(page.getByLabel("Tu cuota decimal")).toHaveValue("");
  await agregar(page);
  await page.goto("/boleto");
  const stored = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("kuota-v1")!),
  );
  expect(stored.boleto).toHaveLength(2);
  const result = await (
    await request.post(`${api}/boleto`, {
      data: { patas: stored.boleto, banca: stored.banca },
    })
  ).json();
  expect(result.resumen.disponible).toBe(true);
  await expect(page.getByTestId("probabilidad-conjunta")).toHaveText(
    `${(result.resumen.prob * 100).toFixed(1)}%`,
  );
  // Ambos mercados comparten resultados: el motor no debe multiplicar marginales.
  expect(
    Math.abs(
      result.resumen.prob - stored.boleto[0].prob * stored.boleto[1].prob,
    ),
  ).toBeGreaterThan(0.001);
  await page.getByText("Banca y Kelly", { exact: true }).click();
  if (!result.stake.disponible)
    await expect(
      page.getByText(result.stake.advertencia, { exact: true }),
    ).toBeVisible();
  else if (result.stake.sin_valor)
    await expect(
      page.getByText("Sin valor en los escenarios de sensibilidad:", {
        exact: false,
      }),
    ).toBeVisible();
  else
    for (const option of result.stake.opciones)
      await expect(
        page
          .getByText("Q" + Math.round(option.monto).toLocaleString("es-GT"), {
            exact: true,
          })
          .first(),
      ).toBeVisible();
});

test("vaciar boleto requiere confirmación y persiste el resultado", async ({
  page,
}) => {
  await analizar(page);
  await agregar(page);
  await page.goto("/boleto");
  await page
    .getByRole("button", { name: "Vaciar boleto", exact: true })
    .click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "¿Eliminar todas las selecciones guardadas?",
  );
  await page
    .getByRole("button", { name: "Conservar boleto", exact: true })
    .click();
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Vaciar boleto", exact: true })
    .click();
  await page.getByRole("button", { name: "Sí, vaciar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Tu boleto está vacío" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Tu boleto está vacío" }),
  ).toBeVisible();
});

test("estadísticas desplegadas: accesibilidad y ancho en pantallas pequeñas y tablet", async ({
  page,
}) => {
  test.setTimeout(120000);
  for (const width of [320, 1024])
    for (const theme of ["light", "dark"] as const) {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
      await analizar(page);
      for (const item of await page.locator("main details").all())
        await item.evaluate((element) => {
          (element as HTMLDetailsElement).open = true;
        });
      await expect(page.getByRole("table").first()).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        `${width}/${theme}`,
      ).toBe(true);
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(
        result.violations,
        JSON.stringify(
          result.violations.map((v) => ({
            id: v.id,
            nodes: v.nodes.map((n) => n.target),
          })),
        ),
      ).toEqual([]);
    }
});
