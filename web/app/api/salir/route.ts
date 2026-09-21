// Cerrar sesión: borra la cookie de acceso y vuelve a la pantalla de contraseña.
import { NextResponse } from "next/server";
import { COOKIE } from "@/lib/gate";

export async function POST(req: Request) {
  const res = NextResponse.redirect(new URL("/", new URL(req.url).origin), 303);
  res.cookies.set(COOKIE, "", { maxAge: 0, path: "/" });
  return res;
}
