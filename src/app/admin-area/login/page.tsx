import { redirect } from "next/navigation";
import { adminUrl, isAdmin } from "@/lib/admin";
import { loginAction } from "../actions";

export default async function Login({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (await isAdmin()) redirect(adminUrl());
  const { error } = await searchParams;
  const needsCode = !!process.env.ADMIN_TOTP_SECRET?.trim();
  return (
    <form action={loginAction} className="form" style={{ maxWidth: 380 }}>
      <h1 style={{ fontSize: "1.8rem" }}>Acceso</h1>
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="field"><label htmlFor="password">Contraseña</label><input id="password" name="password" type="password" required autoComplete="current-password" /></div>
      {needsCode && (
        <div className="field"><label htmlFor="code">Código de verificación</label><input id="code" name="code" type="text" inputMode="numeric" pattern="\d{6}" maxLength={6} required autoComplete="one-time-code" /></div>
      )}
      <button className="btn" type="submit">Entrar</button>
    </form>
  );
}
