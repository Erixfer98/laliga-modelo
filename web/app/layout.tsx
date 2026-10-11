import type { Metadata, Viewport } from "next";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import { BarraInferior, Header } from "@/components/Nav";
import { Puerta } from "@/components/Puerta";
import { autorizado } from "@/lib/gate";

export const metadata: Metadata = {
  title: "Kuota · El fútbol, con perspectiva",
  description: "Poisson + Dixon-Coles para las 5 grandes ligas y Liga MX",
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0b1018",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const ok = await autorizado();
  return (
    <html lang="es" className="h-full" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('kuota-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}",
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        {ok ? (
          <StoreProvider>
            <a href="#contenido" className="skip-link">
              Saltar al contenido
            </a>
            <Header conClave={!!process.env.KUOTA_CLAVE} />
            <main
              id="contenido"
              className="max-w-[1200px] w-full mx-auto px-4 lg:px-6 pb-40 lg:pb-12 pt-6"
            >
              {children}
            </main>
            <BarraInferior />
          </StoreProvider>
        ) : (
          <Puerta />
        )}
      </body>
    </html>
  );
}
