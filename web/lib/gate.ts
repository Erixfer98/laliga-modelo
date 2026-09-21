// Puerta de entrada con una sola contraseña compartida (variable KUOTA_CLAVE en el servidor).
// Si KUOTA_CLAVE no está definida (por ejemplo en tu Mac), la app queda abierta.
import { createHash } from "node:crypto";
import { cookies } from "next/headers";

export const COOKIE = "kuota";
export const firma = (clave: string) => createHash("sha256").update(`kuota:${clave}`).digest("hex");

export async function autorizado(): Promise<boolean> {
  const c = (await cookies()).get(COOKIE)?.value;   // se lee siempre: así la página se sirve al vuelo y nunca queda "congelada" en el build
  const clave = process.env.KUOTA_CLAVE;
  if (!clave) return true;
  return c === firma(clave);
}
