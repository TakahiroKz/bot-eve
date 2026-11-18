import { NextResponse, type NextRequest } from "next/server";
import { adminPath } from "@/lib/env";

const INTERNAL = "/admin-area";

/**
 * El panel vive en `ADMIN_PATH` (URL secreta, mismo dominio) y se sirve desde una carpeta interna.
 * - La ruta interna no es accesible directamente (404).
 * - Toda respuesta del panel lleva `X-Robots-Tag: noindex` y `Cache-Control: no-store`.
 */
export function proxy(req: NextRequest) {
  const ap = adminPath();
  if (ap === INTERNAL) throw new Error("ADMIN_PATH no puede ser " + INTERNAL);
  const path = req.nextUrl.pathname;

  if (path === INTERNAL || path.startsWith(INTERNAL + "/")) {
    return new NextResponse(null, { status: 404 });
  }
  if (path === ap || path.startsWith(ap + "/")) {
    const url = req.nextUrl.clone();
    url.pathname = INTERNAL + path.slice(ap.length);
    const res = NextResponse.rewrite(url);
    res.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
    res.headers.set("Cache-Control", "no-store");
    return res;
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|products/).*)"],
};
