// Recibe la contraseña del formulario, la compara con KUOTA_CLAVE y deja una cookie por 180 días.
import { NextResponse } from "next/server";
import { COOKIE, firma } from "@/lib/gate";

export async function POST(req: Request) {
  const form = await req.formData();
  const clave = String(form.get("clave") ?? "");
  const esperada = process.env.KUOTA_CLAVE ?? "";
  const url = new URL(req.url);
  if (!esperada || clave !== esperada) return NextResponse.redirect(new URL("/?error=1", url.origin), 303);
  const res = NextResponse.redirect(new URL("/", url.origin), 303);
  res.cookies.set(COOKIE, firma(esperada), { httpOnly: true, sameSite: "lax", secure: url.protocol === "https:", maxAge: 180 * 24 * 3600, path: "/" });
  return res;
}
