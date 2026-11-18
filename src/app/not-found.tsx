import Link from "next/link";

export default function NotFound() {
  return (
    <div className="wrap section">
      <p className="eyebrow">404</p>
      <h1 style={{ fontSize: "2.5rem" }}>No encontramos esa página.</h1>
      <Link href="/" className="btn">Volver al inicio</Link>
    </div>
  );
}
