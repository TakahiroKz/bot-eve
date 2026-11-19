import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPolicies, POLICY_SLUGS, POLICY_UPDATED } from "@/lib/policies";
import { getSettings } from "@/lib/settings";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = getPolicies(await getSettings())[(await params).slug];
  return p ? { title: p.title, description: p.summary } : {};
}

export default async function Policy({ params }: Props) {
  const { slug } = await params;
  const policies = getPolicies(await getSettings());
  const p = policies[slug];
  if (!p) notFound();
  return (
    <div className="wrap section">
      <div className="prose">
        <p className="eyebrow">Información legal</p>
        <h1 style={{ fontSize: "2.5rem" }}>{p.title}</h1>
        <p className="muted">Última actualización: {POLICY_UPDATED}.</p>
        {p.sections.map((sec) => (
          <section key={sec.h}>
            <h2>{sec.h}</h2>
            {sec.p?.map((t) => <p key={t}>{t}</p>)}
            {sec.ul && <ul>{sec.ul.map((t) => <li key={t}>{t}</li>)}</ul>}
          </section>
        ))}
        <hr style={{ margin: "2.5rem 0 1rem", borderColor: "rgba(128,128,128,.3)" }} />
        <p className="muted">
          Otras políticas:{" "}
          {POLICY_SLUGS.filter((k) => k !== slug).map((k, i) => (
            <span key={k}>{i > 0 && " · "}<Link href={`/politicas/${k}`}>{policies[k].title}</Link></span>
          ))}
        </p>
      </div>
    </div>
  );
}
