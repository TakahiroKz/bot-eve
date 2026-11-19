import { requireAdmin } from "@/lib/admin";
import { getSettings } from "@/lib/settings";
import { saveSettingsAction } from "../actions";

export default async function SettingsPage({ searchParams }: { searchParams: Promise<{ error?: string; ok?: string }> }) {
  await requireAdmin();
  const { error, ok } = await searchParams;
  const s = await getSettings();
  return (
    <>
      <h1 style={{ fontSize: "2rem" }}>Ajustes</h1>
      {error && <p className="notice error" role="alert">{error}</p>}
      {ok && <p className="notice ok">{ok}</p>}
      <form action={saveSettingsAction} className="form">
        <h2 style={{ fontSize: "1.1rem" }}>Tienda</h2>
        <div className="field"><label>Nombre de la tienda</label><input type="text" name="store_name" defaultValue={s.storeName} /></div>
        <div className="field"><label>Correo de contacto</label><input type="email" name="support_email" defaultValue={s.supportEmail} /></div>
        <h2 style={{ fontSize: "1.1rem" }}>Datos legales del vendedor</h2>
        <p className="muted">Se muestran en los términos, la política de datos y la de cambios. La ley de comercio electrónico exige identificar al vendedor: completa estos campos.</p>
        <div className="row">
          <div className="field"><label>Nombre completo del titular</label><input type="text" name="legal_name" defaultValue={s.legalName} autoComplete="off" /></div>
          <div className="field"><label>Documento (C.C. o NIT)</label><input type="text" name="legal_id" defaultValue={s.legalId} autoComplete="off" /></div>
          <div className="field"><label>Dirección</label><input type="text" name="legal_address" defaultValue={s.legalAddress} autoComplete="off" /></div>
          <div className="field"><label>Ciudad y departamento</label><input type="text" name="legal_city" defaultValue={s.legalCity} autoComplete="off" /></div>
        </div>
        <h2 style={{ fontSize: "1.1rem" }}>Envíos</h2>
        <div className="row">
          <div className="field"><label>Tarifa de envío (COP)</label><input type="number" name="shipping_fee" min={0} step={500} defaultValue={s.shippingFee} /></div>
          <div className="field"><label>Envío gratis desde (prendas)</label><input type="number" name="free_shipping_min_items" min={1} defaultValue={s.freeShippingMinItems} /></div>
          <div className="field"><label>Días hábiles de entrega</label><input type="number" name="delivery_days" min={1} defaultValue={s.deliveryDays} /></div>
        </div>
        <h2 style={{ fontSize: "1.1rem" }}>WhatsApp</h2>
        <p className="muted">Con número vacío el botón no se muestra. Incluye el indicativo (Colombia: 57).</p>
        <div className="row">
          <div className="field"><label>Número</label><input type="tel" name="whatsapp" defaultValue={s.whatsapp} placeholder="573001234567" /></div>
          <div className="field"><label>Mensaje inicial</label><input type="text" name="whatsapp_message" defaultValue={s.whatsappMessage} /></div>
        </div>
        <h2 style={{ fontSize: "1.1rem" }}>Redes sociales</h2>
        <p className="muted">Solo se muestran las que tengan enlace (https://…).</p>
        <div className="row">
          <div className="field"><label>Instagram</label><input type="url" name="instagram" defaultValue={s.instagram} /></div>
          <div className="field"><label>TikTok</label><input type="url" name="tiktok" defaultValue={s.tiktok} /></div>
          <div className="field"><label>Facebook</label><input type="url" name="facebook" defaultValue={s.facebook} /></div>
          <div className="field"><label>YouTube</label><input type="url" name="youtube" defaultValue={s.youtube} /></div>
          <div className="field"><label>X</label><input type="url" name="x" defaultValue={s.x} /></div>
        </div>
        <div><button className="btn" type="submit">Guardar ajustes</button></div>
      </form>
    </>
  );
}
