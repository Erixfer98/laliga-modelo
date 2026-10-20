// La pantalla de partido ahora es la principal (/). Se mantiene esta ruta para enlaces viejos.
import { redirect } from "next/navigation";

export default function PartidoViejo() {
  redirect("/");
}
