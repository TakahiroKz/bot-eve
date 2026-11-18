import type { Metadata } from "next";
import Link from "next/link";
import { adminUrl, isAdmin } from "@/lib/admin";
import { logoutAction } from "./actions";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Panel",
  robots: { index: false, follow: false, nocache: true, googleBot: { index: false, follow: false } },
};

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const logged = await isAdmin();
  return (
    <>
      <div className="admin-bar">
        <div className="wrap">
          <b>Panel</b>
          {logged && (
            <>
              <Link href={adminUrl()}>Resumen</Link>
              <Link href={adminUrl("/pedidos")}>Pedidos</Link>
              <Link href={adminUrl("/productos")}>Productos</Link>
              <Link href={adminUrl("/inventario")}>Inventario</Link>
              <Link href={adminUrl("/ajustes")}>Ajustes</Link>
              <form action={logoutAction} className="push"><button className="link-btn" type="submit">Salir</button></form>
            </>
          )}
        </div>
      </div>
      <main className="wrap section" style={{ paddingTop: "2rem" }}>{children}</main>
    </>
  );
}
