import { Footer, Header, WhatsAppButton } from "@/components/SiteChrome";

export const dynamic = "force-dynamic";

export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a className="skip" href="#contenido">Saltar al contenido</a>
      <Header />
      <main id="contenido">{children}</main>
      <Footer />
      <WhatsAppButton />
    </>
  );
}
