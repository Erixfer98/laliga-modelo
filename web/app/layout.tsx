import type { Metadata, Viewport } from "next";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import { BarraInferior, Header } from "@/components/Nav";
import { Puerta } from "@/components/Puerta";
import { autorizado } from "@/lib/gate";

export const metadata: Metadata = {
  title: "Kuota · Parlays con datos",
  description: "Poisson + Dixon-Coles para las 5 grandes ligas y Liga MX",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#0a0d14" };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const ok = await autorizado();
  return (
    <html lang="es" className="h-full">
      <body className="min-h-full flex flex-col">
        {ok ? (
          <StoreProvider>
            <Header />
            <main className="max-w-[640px] w-full mx-auto px-4 pb-24 sm:pb-10 pt-1">{children}</main>
            <BarraInferior />
          </StoreProvider>
        ) : <Puerta />}
      </body>
    </html>
  );
}
