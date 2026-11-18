import Link from "next/link";
import { readCart } from "@/lib/cart";
import { getSettings, safeUrl } from "@/lib/settings";

export async function Header() {
  const [s, cart] = await Promise.all([getSettings(), readCart()]);
  const count = cart.reduce((n, l) => n + l.qty, 0);
  return (
    <header className="site-header">
      <div className="wrap">
        <Link href="/" className="brand">{s.storeName}</Link>
        <nav className="nav" aria-label="Principal">
          <Link href="/hombre">Hombre</Link>
          <Link href="/mujer">Mujer</Link>
          <Link href="/carrito" className="cart-link">
            Carrito{count > 0 && <span className="cart-count" aria-label={`${count} prendas`}>{count}</span>}
          </Link>
        </nav>
      </div>
    </header>
  );
}

const SOCIALS = [
  ["instagram", "Instagram"],
  ["tiktok", "TikTok"],
  ["facebook", "Facebook"],
  ["youtube", "YouTube"],
  ["x", "X"],
] as const;

export async function Footer() {
  const s = await getSettings();
  const links = SOCIALS.map(([k, label]) => ({ label, href: safeUrl(s[k]) })).filter((l) => l.href);
  return (
    <footer className="site-footer">
      <div className="wrap cols">
        <div>
          <h4>{s.storeName}</h4>
          <p>Diseñada para quien no necesita explicarse.</p>
          <p>Entrega en {s.deliveryDays} días hábiles en Colombia.</p>
        </div>
        <div>
          <h4>Ayuda</h4>
          <ul>
            <li><Link href="/politicas/cambios">Cambios y devoluciones</Link></li>
            <li><Link href="/politicas/datos">Tratamiento de datos</Link></li>
            <li><Link href="/politicas/terminos">Términos y condiciones</Link></li>
            {s.supportEmail && <li><a href={`mailto:${s.supportEmail}`}>{s.supportEmail}</a></li>}
          </ul>
        </div>
        {links.length > 0 && (
          <div>
            <h4>Síguenos</h4>
            <ul>
              {links.map((l) => (
                <li key={l.label}><a href={l.href} target="_blank" rel="noopener noreferrer">{l.label}</a></li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </footer>
  );
}

export async function WhatsAppButton() {
  const s = await getSettings();
  if (!s.whatsapp) return null;
  const href = `https://wa.me/${s.whatsapp}?text=${encodeURIComponent(s.whatsappMessage)}`;
  return (
    <a className="whatsapp" href={href} target="_blank" rel="noopener noreferrer" aria-label="Escríbenos por WhatsApp">
      <svg viewBox="0 0 32 32" fill="currentColor" aria-hidden="true">
        <path d="M16.04 3C9.4 3 4 8.38 4 15.02c0 2.12.55 4.18 1.6 6L4 29l8.17-1.57a12 12 0 0 0 5.87 1.5h.01C24.68 28.93 30 23.55 30 16.9 30 10.4 24.7 3 16.04 3Zm0 22.9h-.01a10 10 0 0 1-5.1-1.4l-.37-.22-4.85.93.98-4.73-.24-.38a9.9 9.9 0 0 1-1.52-5.27c0-5.5 4.5-9.97 10.03-9.97 2.68 0 5.2 1.04 7.09 2.93a9.9 9.9 0 0 1 2.93 7.05c0 5.5-4.5 10.06-9.94 10.06Zm5.46-7.46c-.3-.15-1.77-.87-2.04-.97s-.47-.15-.67.15-.77.97-.95 1.17-.35.22-.65.07a8.2 8.2 0 0 1-2.4-1.48 9 9 0 0 1-1.66-2.07c-.17-.3 0-.46.13-.6.13-.13.3-.35.45-.52.15-.18.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.62-.92-2.22-.24-.58-.49-.5-.67-.5h-.57c-.2 0-.52.08-.8.37s-1.05 1.03-1.05 2.5 1.08 2.9 1.23 3.1c.15.2 2.1 3.2 5.1 4.48.71.31 1.27.5 1.7.63.72.23 1.37.2 1.88.12.57-.08 1.77-.72 2.02-1.42.25-.7.25-1.3.17-1.42-.07-.13-.27-.2-.57-.35Z" />
      </svg>
    </a>
  );
}
