const { chromium, expect } = require("@playwright/test");
const fs = require("fs");
(async () => {
  const b = await chromium.launch({
    executablePath:
      process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
  });
  const rows = [];
  for (const width of [390, 1440]) {
    const page = await b.newPage({ viewport: { width, height: 900 } });
    let reqs = [];
    page.on("request", (r) => {
      if (/\/liga\/[^/]+\/partido\?/.test(r.url())) reqs.push(r.url());
    });
    await page.goto(
      (process.env.BENCHMARK_URL || "http://127.0.0.1:3103") + "/partido",
    );
    await page.getByTestId("probabilidad-seleccionada").waitFor();
    await expect(
      page.getByText("Actualizando detalle histórico…", { exact: true }),
    ).not.toBeVisible();
    async function measure(kind, action, ready) {
      let before = reqs.length,
        t = 0;
      await page.evaluate(() => {
        window.__kuotaVisual = null;
        document.addEventListener(
          "pointerdown",
          () => {
            const snapshot = () => {
              const p = document.querySelector(
                '[data-testid="probabilidad-seleccionada"]',
              );
              if (!p || p.textContent.trim() === "…") return null;
              return (
                document.querySelector('[data-testid="mercado-seleccionado"]')
                  ?.textContent +
                "|" +
                p.textContent +
                "|" +
                document.querySelector("#seleccion .tag")?.textContent
              );
            };
            const inicial = snapshot(),
              start = performance.now();
            const observer = new MutationObserver(() => {
              const now = snapshot();
              if (now && now !== inicial) {
                observer.disconnect();
                requestAnimationFrame(() =>
                  requestAnimationFrame(() => {
                    window.__kuotaVisual = performance.now() - start;
                  }),
                );
              }
            });
            observer.observe(document.body, {
              subtree: true,
              childList: true,
              characterData: true,
            });
          },
          { once: true, capture: true },
        );
      });
      t = performance.now();
      await action();
      await ready();
      await page.evaluate(
        () =>
          new Promise((r) =>
            requestAnimationFrame(() => requestAnimationFrame(r)),
          ),
      );
      await page.waitForFunction(() => window.__kuotaVisual !== null);
      const visible_ms = await page.evaluate(() => window.__kuotaVisual);
      rows.push({
        visible_ms,
        width,
        kind,
        ms: performance.now() - t,
        requests: reqs
          .slice(before)
          .map((u) => new URL(u).searchParams.get("modo") || "completo"),
      });
    }
    const groups = page.getByRole("group", {
      name: "Grupo de mercados",
      exact: true,
    });
    const markets = page.getByRole("group", {
      name: "Seleccionar mercado",
      exact: true,
    });
    for (let i = 0; i < 10; i++) {
      await measure(
        "mercado",
        () =>
          markets
            .getByRole("button")
            .nth((i + 1) % 2)
            .click(),
        () =>
          expect(markets.getByRole("button").nth((i + 1) % 2)).toHaveAttribute(
            "aria-pressed",
            "true",
          ),
      );
    }
    for (let i = 0; i < 10; i++) {
      const name = i % 2 ? "Resultado" : "Total";
      await measure(
        "grupo",
        () => groups.getByRole("button", { name, exact: true }).click(),
        () =>
          expect(markets.getByRole("button").first()).toContainText(
            i % 2 ? "Gana" : "Total",
          ),
      );
    }
    await groups.getByRole("button", { name: "Total", exact: true }).click();
    await page
      .getByText("Ajustar líneas e historial", { exact: false })
      .click();
    for (let i = 0; i < 10; i++) {
      const old = await markets.getByRole("button").first().innerText();
      await measure(
        "linea",
        () =>
          page
            .getByLabel(i % 2 ? "Reducir línea" : "Aumentar línea", {
              exact: true,
            })
            .click(),
        () => expect(markets.getByRole("button").first()).not.toHaveText(old),
      );
    }
    for (let i = 0; i < 10; i++) {
      const name = i % 2 ? "Goles" : "Corners";
      await measure(
        "metrica",
        () =>
          page
            .getByRole("group", { name: "Métrica del análisis", exact: true })
            .getByRole("button", { name, exact: true })
            .click(),
        () =>
          expect(page.getByTestId("probabilidad-seleccionada")).not.toHaveText(
            "…",
          ),
      );
    }
    await page.close();
  }
  fs.writeFileSync(process.argv[2], JSON.stringify(rows, null, 2));
  console.log(`${rows.length} interacciones registradas`);
  await b.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
