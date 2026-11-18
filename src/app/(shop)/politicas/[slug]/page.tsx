import type { Metadata } from "next";
import { notFound } from "next/navigation";

const PAGES: Record<string, { title: string; body: string[] }> = {
  cambios: {
    title: "Cambios y devoluciones",
    body: [
      "Texto provisional: la política de cambios y devoluciones está pendiente de definir.",
      "Esta página debe cumplir el derecho de retracto en ventas a distancia (Ley 1480 de 2011) y explicar plazos, condiciones de la prenda y quién asume el costo del envío.",
    ],
  },
  datos: {
    title: "Tratamiento de datos personales",
    body: [
      "Texto provisional: la política de tratamiento de datos (Ley 1581 de 2012) está pendiente de redactar.",
      "Debe indicar responsable, finalidades, derechos del titular y canal para ejercerlos.",
    ],
  },
  terminos: {
    title: "Términos y condiciones",
    body: ["Texto provisional: los términos y condiciones están pendientes de redactar."],
  },
};

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = PAGES[(await params).slug];
  return p ? { title: p.title, robots: { index: false } } : {};
}

export default async function Policy({ params }: Props) {
  const p = PAGES[(await params).slug];
  if (!p) notFound();
  return (
    <div className="wrap section">
      <div className="prose">
        <h1 style={{ fontSize: "2.5rem" }}>{p.title}</h1>
        {p.body.map((t) => <p key={t} className="muted">{t}</p>)}
      </div>
    </div>
  );
}
