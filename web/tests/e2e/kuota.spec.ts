import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const api = "http://127.0.0.1:8000";
const runtimeErrors = new WeakMap<Page, string[]>();

/** Abre la pantalla de partido y la hoja de un mercado (por defecto, el primero del total). */
async function abrir(page: Page, grupo: string | RegExp = /^Total de /, mercado?: string) {
  if (!(await page.getByTestId("lambdas").isVisible())) await page.goto("/");
  await expect(page.getByTestId("lambdas")).toBeVisible();
  const filas = page.getByRole("region", { name: grupo }).getByTestId("fila-mercado");
  await (mercado ? filas.filter({ hasText: mercado }).first() : filas.first()).click();
  await expect(page.getByTestId("mercado-seleccionado")).toBeVisible();
}
async function agregar(page: Page) {
  await page.getByLabel("Cuota de la casa").fill("1.90");
  await page.getByRole("button", { name: "Agregar al boleto", exact: true }).click();
  await expect(page.getByRole("button", { name: "Ya está en tu boleto" })).toBeDisabled();
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
}
const metricas = (page: Page) => page.getByRole("group", { name: "Métrica", exact: true });

test.beforeEach(async ({ page }) => {
  await page.request.post("/api/entrar", { form: { clave: "kuota-e2e-access" } });
  // Fallos de ejecución son regresiones; errores de recursos externos no se sustituyen.
  const errors: string[] = [];
  runtimeErrors.set(page, errors);
  page.on("pageerror", (e) => errors.push(e.message));
});
test.afterEach(async ({ page }) => {
  expect(runtimeErrors.get(page) ?? [], "Errores de JavaScript en la página").toEqual([]);
});

test("autenticación: puerta, contraseña incorrecta, entrada y salida", async ({ browser }) => {
  const c = await browser.newContext();
  const p = await c.newPage();
  await p.goto("http://127.0.0.1:3100");
  await expect(p.getByLabel("Contraseña de acceso")).toBeVisible();
  await p.getByLabel("Contraseña de acceso").fill("incorrecta");
  await p.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(p.getByText("Contraseña incorrecta", { exact: true })).toBeVisible();
  await p.getByLabel("Contraseña de acceso").fill("kuota-e2e-access");
  await p.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(p.getByTestId("lambdas")).toBeVisible();
  await p.getByRole("link", { name: "Más", exact: true }).first().click();
  await p.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(p.getByLabel("Contraseña de acceso")).toBeVisible();
  await c.close();
});

test("navegación: tres pestañas, Más y rutas viejas", async ({ page }, info) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", {
    name: info.project.name === "iphone" ? "Navegación móvil" : "Navegación principal",
  });
  await expect(nav.getByRole("link")).toHaveText([/Partido/, /Boleto/, /Más/]);
  await nav.getByRole("link", { name: "Más" }).click();
  await expect(page).toHaveURL(/\/mas$/);
  await page.getByRole("link", { name: /Tabla de posiciones/ }).click();
  await expect(page).toHaveURL(/\/tabla$/);
  await expect(page.getByRole("heading", { name: "Tabla de posiciones." })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Más" })).toHaveAttribute("aria-current", "page");
  for (const path of ["/cara", "/diccionario", "/boleto", "/liga", "/mas"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toBeVisible();
  }
  await page.goto("/partido");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("lambdas")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Saltar al contenido" })).toBeFocused();
});

test("la tabla y la hoja muestran los números del motor; EV con la cuota", async ({ page, request }) => {
  await abrir(page);
  await expect(page.getByLabel("Cuota de la casa")).toHaveValue("");
  await expect(page.getByRole("button", { name: "Agregar al boleto", exact: true })).toBeDisabled();
  const local = await page.getByLabel("Equipo local", { exact: true }).inputValue();
  const visitante = await page.getByLabel("Equipo visitante", { exact: true }).inputValue();
  const nombre = await page.getByTestId("mercado-seleccionado").innerText();
  const v = await (
    await request.get(`${api}/liga/laliga/partido`, { params: { local, visitante, met: "goles", modo: "compacto" } })
  ).json();
  const m = v.mercados.find((x: { mercado: string }) => x.mercado === nombre);
  await expect(page.getByTestId("probabilidad-seleccionada")).toHaveText(`${(m.prob * 100).toFixed(1)}%`);
  await expect(page.getByTestId("lambdas")).toContainText(v.lambda_local.toFixed(2));
  await expect(page.getByTestId("lambdas")).toContainText(v.lambda_visitante.toFixed(2));
  await page.getByLabel("Cuota de la casa").fill("1");
  await expect(page.getByRole("button", { name: "Agregar al boleto", exact: true })).toBeDisabled();
  await page.getByLabel("Cuota de la casa").fill("1.90");
  const ev = m.prob * 1.9 + m.push - 1;
  await expect(page.getByTestId("ev")).toHaveText((ev >= 0 ? "+" : "") + ev.toFixed(2));
  await agregar(page);
  await page.goto("/boleto");
  await expect(page.getByTestId("probabilidad-conjunta")).toBeVisible();
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("kuota-v1")!));
  const result = await (await request.post(`${api}/boleto`, { data: { patas: stored.boleto, banca: stored.banca } })).json();
  await expect(page.getByTestId("probabilidad-conjunta")).toHaveText(`${(result.resumen.prob * 100).toFixed(1)}%`);
});

test("las 9 métricas se cargan una vez; cambiar de métrica no vuelve a pedir", async ({ page }) => {
  const pedidos: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("modo=compacto")) pedidos.push(new URL(r.url()).searchParams.get("met")!);
  });
  await page.goto("/");
  await expect(page.getByTestId("lambdas")).toBeVisible();
  await expect.poll(() => new Set(pedidos).size, { timeout: 30000 }).toBe(9);
  const antes = pedidos.length;
  for (const name of ["Goles 1T", "Goles 2T", "Tiros", "Tiros a puerta", "Corners", "Faltas", "Amarillas", "Rojas", "Goles"]) {
    await metricas(page).getByRole("button", { name, exact: true }).click();
    await expect(metricas(page).getByRole("button", { name, exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("lambdas")).toBeVisible();
    await expect(page.getByTestId("fila-mercado").first()).toBeVisible();
  }
  expect(pedidos.length).toBe(antes);
});

test("últimos 10, casa/fuera y más líneas", async ({ page }) => {
  await page.goto("/");
  const total = page.getByRole("region", { name: /^Total de / });
  await expect(total.getByTestId("fila-mercado").first()).toBeVisible();
  await page.getByRole("button", { name: "Últ. 10", exact: true }).click();
  await expect(total.getByTestId("fila-mercado").first()).toContainText(/\/10/);
  await page.getByRole("button", { name: "Casa / fuera", exact: true }).click();
  await expect(page.getByRole("button", { name: "Casa / fuera", exact: true })).toHaveAttribute("aria-pressed", "true");
  const antes = await total.getByTestId("fila-mercado").count();
  await total.getByRole("button", { name: "Más líneas" }).click();
  await expect.poll(() => total.getByTestId("fila-mercado").count()).toBe(antes + 2);
});

test("cambio de equipos y métrica no conserva la cuota de otro mercado", async ({ page }) => {
  await abrir(page);
  await page.getByLabel("Cuota de la casa").fill("2.10");
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await metricas(page).getByRole("button", { name: "Corners", exact: true }).click();
  await abrir(page, /^Total de corners/);
  await expect(page.getByLabel("Cuota de la casa")).toHaveValue("");
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page.getByLabel("Equipo local", { exact: true }).selectOption("Barcelona");
  await expect(page.getByLabel("Equipo visitante", { exact: true })).not.toHaveValue("Barcelona");
  await expect(page.getByRole("region", { name: "Corners de Barcelona" })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Equipo local", { exact: true })).toHaveValue("Barcelona");
});

test("los datos de otra liga no aparecen mientras carga la nueva", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("lambdas")).toBeVisible();
  await page.route("**/liga/premier/partido?**", async (route) => {
    await new Promise((r) => setTimeout(r, 1200));
    await route.continue().catch(() => {});
  });
  const premier = page.getByRole("group", { name: "Elegir liga" }).getByRole("button", { name: "Premier League", exact: true });
  await premier.click();
  await expect(page.getByTestId("lambdas")).not.toBeVisible();
  await expect(page.getByTestId("lambdas")).toBeVisible();
  await expect(premier).toHaveAttribute("aria-pressed", "true");
});

test("cara a cara del partido en la misma pantalla", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByTestId("lambdas")).toBeVisible();
  const local = await page.getByLabel("Equipo local", { exact: true }).inputValue();
  const visitante = await page.getByLabel("Equipo visitante", { exact: true }).inputValue();
  const c = await (await request.get(`${api}/liga/laliga/cara`, { params: { local, visitante } })).json();
  const cara = page.getByRole("region", { name: "Cara a cara" });
  await expect(cara).toBeVisible();
  if (c.partidos.length) await expect(cara.getByRole("listitem")).toHaveCount(c.partidos.length);
  else await expect(cara).toContainText("No se enfrentaron");
});

test("boleto persiste, agrupa y permite quitar; vacío útil", async ({ page }) => {
  await abrir(page);
  await agregar(page);
  await expect(page.getByRole("region", { name: /^Total de / }).getByTestId("fila-mercado").first()).toContainText("●");
  await page.goto("/boleto");
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await expect(page.getByText("1 selección · boleto guardado en este dispositivo", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page.getByRole("button", { name: /^Quitar / }).click();
  await expect(page.getByRole("heading", { name: "Tu boleto está vacío" })).toBeVisible();
});

test("métricas correlacionadas sin modelo y selecciones antiguas no inventan resultado", async ({ page }) => {
  await abrir(page);
  await agregar(page);
  await metricas(page).getByRole("button", { name: "Corners", exact: true }).click();
  await abrir(page, /^Total de corners/);
  await expect(page.getByLabel("Cuota de la casa")).toHaveValue("");
  await agregar(page);
  await page.goto("/boleto");
  await expect(page.getByRole("heading", { name: "Cálculo conjunto no disponible" })).toBeVisible();
  await expect(page.getByTestId("probabilidad-conjunta")).not.toBeVisible();
  await expect(page.getByText("Métricas distintas del mismo partido:", { exact: false }).first()).toBeVisible();
  await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem("kuota-v1")!);
    delete s.boleto[0].seleccion;
    s.boleto = s.boleto.slice(0, 1);
    localStorage.setItem("kuota-v1", JSON.stringify(s));
  });
  await page.reload();
  await expect(page.getByText("Selección antigua o sin identidad verificable:", { exact: false }).first()).toBeVisible();
});

test("errores y reintentos conservan las selecciones", async ({ page }) => {
  await abrir(page);
  await agregar(page);
  await page.route("**/boleto", (route) =>
    route.request().method() === "POST" ? route.fulfill({ status: 503, body: "offline" }) : route.continue(),
  );
  await page.goto("/boleto");
  await expect(page.getByRole("heading", { name: "No pudimos calcular el boleto" })).toBeVisible();
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page.unroute("**/boleto");
  await page.getByRole("button", { name: "Reintentar cálculo" }).click();
  await expect(page.getByTestId("probabilidad-conjunta")).toBeVisible();
  await page.route("**/liga/laliga/partido?**", (route) => route.fulfill({ status: 503, body: "offline" }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "No pudimos cargar los datos" })).toBeVisible();
  await page.unroute("**/liga/laliga/partido?**");
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(page.getByTestId("lambdas")).toBeVisible();
});

test("glosario, ausencia de resultados y tema persistido", async ({ page }) => {
  await page.goto("/diccionario");
  await page.getByLabel("Buscar en el glosario").fill("zzzz-no-existe");
  await expect(page.getByRole("status")).toContainText("No hay términos");
  await page.getByLabel("Buscar en el glosario").fill("Kelly");
  await expect(page.locator("summary").filter({ hasText: "Kelly" }).first()).toBeVisible();
  await page.goto("/mas");
  await page.getByLabel("Apariencia", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

for (const theme of ["light", "dark"] as const)
  test(`accesibilidad AA y ausencia de overflow: ${theme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
    for (const path of ["/", "/liga", "/mas", "/boleto", "/tabla", "/cara", "/diccionario"]) {
      await page.goto(path);
      if (path === "/") await expect(page.getByTestId("fila-mercado").first()).toBeVisible();
      else if (path === "/liga") await expect(page.getByText("Último partido registrado:", { exact: false })).toBeVisible();
      else if (path === "/mas") await expect(page.getByRole("heading", { name: "Más" })).toBeVisible();
      else if (path === "/tabla") await expect(page.getByLabel("Temporada", { exact: true })).toBeVisible();
      else if (path === "/cara") await expect(page.getByRole("heading", { name: "Récord directo" })).toBeVisible();
      else if (path === "/diccionario") await expect(page.getByRole("heading", { name: "Modelo", exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), path).toBe(true);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      expect(
        result.violations,
        `${path}: ${JSON.stringify(result.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })))}`,
      ).toEqual([]);
    }
  });

test("mercados compatibles del mismo partido conservan cálculo conjunto y Kelly", async ({ page, request }) => {
  await abrir(page);
  const local = await page.getByLabel("Equipo local", { exact: true }).inputValue();
  await agregar(page);
  await abrir(page, "Resultado", `${local} o empate`);
  await expect(page.getByLabel("Cuota de la casa")).toHaveValue("");
  await agregar(page);
  await page.goto("/boleto");
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("kuota-v1")!));
  expect(stored.boleto).toHaveLength(2);
  const result = await (await request.post(`${api}/boleto`, { data: { patas: stored.boleto, banca: stored.banca } })).json();
  expect(result.resumen.disponible).toBe(true);
  await expect(page.getByTestId("probabilidad-conjunta")).toHaveText(`${(result.resumen.prob * 100).toFixed(1)}%`);
  // Ambos mercados comparten resultados: el motor no debe multiplicar marginales.
  expect(Math.abs(result.resumen.prob - stored.boleto[0].prob * stored.boleto[1].prob)).toBeGreaterThan(0.001);
  await page.getByText("Banca y Kelly", { exact: true }).click();
  if (!result.stake.disponible) await expect(page.getByText(result.stake.advertencia, { exact: true })).toBeVisible();
  else if (result.stake.sin_valor)
    await expect(page.getByText("Sin valor en los escenarios de sensibilidad:", { exact: false })).toBeVisible();
  else
    for (const option of result.stake.opciones)
      await expect(page.getByText("Q" + Math.round(option.monto).toLocaleString("es-GT"), { exact: true }).first()).toBeVisible();
});

test("vaciar boleto requiere confirmación y persiste el resultado", async ({ page }) => {
  await abrir(page);
  await agregar(page);
  await page.goto("/boleto");
  await page.getByRole("button", { name: "Vaciar boleto", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("¿Eliminar todas las selecciones guardadas?");
  await page.getByRole("button", { name: "Conservar boleto", exact: true }).click();
  await expect(page.getByTestId("seleccion-boleto")).toHaveCount(1);
  await page.getByRole("button", { name: "Vaciar boleto", exact: true }).click();
  await page.getByRole("button", { name: "Sí, vaciar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Tu boleto está vacío" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Tu boleto está vacío" })).toBeVisible();
});

test("hoja con partido a partido: accesibilidad y ancho en celular chico y tablet", async ({ page }) => {
  test.setTimeout(120000);
  for (const width of [320, 1024])
    for (const theme of ["light", "dark"] as const) {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
      await page.goto("/");
      await abrir(page);
      await page.getByRole("button", { name: "Ver partido a partido" }).click();
      await expect(page.getByRole("dialog").getByText("cumplió").first()).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${width}/${theme}`).toBe(true);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      expect(
        result.violations,
        JSON.stringify(result.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) }))),
      ).toEqual([]);
    }
});
