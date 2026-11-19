import { formatCop } from "./pricing";
import type { Settings } from "./settings";

/**
 * Textos legales de la tienda. Los datos variables (tarifa de envío, días de entrega, correo de contacto, identificación
 * del titular) salen de Ajustes, así que cambian solos cuando se editan en el panel.
 * IMPORTANTE: es un texto base alineado con la normativa colombiana aplicable a comercio electrónico; conviene que un
 * abogado lo revise antes de lanzar (en especial la identificación del vendedor y los plazos que la tienda se compromete a cumplir).
 */
export interface PolicySection {
  h: string;
  p?: string[];
  ul?: string[];
}
export interface Policy {
  slug: string;
  title: string;
  summary: string;
  sections: PolicySection[];
}

export const POLICY_UPDATED = "19 de noviembre de 2026";
export const POLICY_SLUGS = ["terminos", "cambios", "envios", "datos"] as const;

/** Identificación del vendedor/responsable: usa los datos de Ajustes; si faltan, no se inventa nada. */
export function sellerIdentity(s: Settings): string {
  const parts = [s.legalName, s.legalId && `identificado(a) con ${s.legalId}`, s.legalAddress && `con domicilio en ${s.legalAddress}`, s.legalCity].filter(Boolean);
  if (s.legalName) return `${parts.join(", ")}, quien opera la tienda en línea ${s.storeName} (en adelante, «${s.storeName}», «nosotros» o «el vendedor»)`;
  return `la persona natural titular de la tienda en línea ${s.storeName} (en adelante, «${s.storeName}», «nosotros» o «el vendedor»), cuyos datos de identificación se informan en cada factura o comprobante y pueden solicitarse en ${s.supportEmail}`;
}

export function getPolicies(s: Settings): Record<string, Policy> {
  const mail = s.supportEmail;
  const store = s.storeName;
  const days = s.deliveryDays;
  const fee = formatCop(s.shippingFee);
  const free = s.freeShippingMinItems;
  const who = sellerIdentity(s);

  const terminos: Policy = {
    slug: "terminos",
    title: "Términos y condiciones",
    summary: `Reglas que aplican a las compras en ${store}.`,
    sections: [
      {
        h: "1. Quién vende",
        p: [`Este sitio web lo opera ${who}. Para cualquier consulta, solicitud o reclamo puede escribir a ${mail}.`],
      },
      {
        h: "2. Aceptación",
        p: [
          `Al navegar por el sitio y al realizar una compra usted declara que leyó y acepta estos términos y condiciones, la política de cambios y devoluciones, la política de envíos y la política de tratamiento de datos personales. Si no está de acuerdo, le pedimos no realizar la compra.`,
          `Para comprar debe ser mayor de edad y tener capacidad legal para contratar.`,
        ],
      },
      {
        h: "3. Productos",
        p: [
          `Describimos cada chaqueta con la mayor precisión posible (modelo, color, tallas y precio). Las fotografías son referenciales: el tono puede variar levemente según la pantalla y la iluminación.`,
          `La disponibilidad se muestra por talla y se actualiza en tiempo real. Un producto agotado no puede comprarse.`,
        ],
      },
      {
        h: "4. Precios",
        p: [
          `Los precios se expresan en pesos colombianos (COP). El valor del envío y el total a pagar se muestran antes de confirmar el pedido. El precio que se cobra es el vigente en el momento de crear el pedido.`,
          `Podemos modificar precios y productos en cualquier momento; los cambios no afectan pedidos ya confirmados.`,
        ],
      },
      {
        h: "5. Cómo se realiza una compra",
        ul: [
          `Usted elige modelo y talla, los agrega al carrito y completa sus datos de envío.`,
          `Al crear el pedido reservamos las unidades por 15 minutos para que pueda pagar. Si el pago no se confirma en ese lapso, la reserva se libera y el pedido expira.`,
          `El pedido queda confirmado únicamente cuando el proveedor de pagos nos informa que el pago fue aprobado. Recibirá un correo de confirmación en la dirección que registró.`,
          `Usted es responsable de que los datos que ingresa (nombre, correo, teléfono y dirección) sean correctos y completos.`,
        ],
      },
      {
        h: "6. Medios de pago",
        p: [
          `El pago se realiza a través de una pasarela de pagos de un tercero, con los medios que se muestren en el momento de pagar (por ejemplo, tarjetas, PSE o billeteras digitales). ${store} no recibe ni almacena los datos de su tarjeta ni de su cuenta bancaria: se ingresan directamente en el entorno del proveedor de pagos.`,
          `Si el pago es rechazado o no se completa, el pedido no se confirma y no se realiza ningún cobro.`,
        ],
      },
      {
        h: "7. Envíos y entrega",
        p: [`Las condiciones de envío (cobertura, costo y plazo) están en la política de envíos, que hace parte de estos términos.`],
      },
      {
        h: "8. Retracto, cambios y garantía",
        p: [`Usted tiene los derechos de retracto, garantía y reversión del pago que reconoce la Ley 1480 de 2011 (Estatuto del Consumidor). Cómo ejercerlos se explica en la política de cambios y devoluciones.`],
      },
      {
        h: "9. Falta de inventario o imposibilidad de entrega",
        p: [`Si, por un error en el inventario o por cualquier otra causa, no podemos entregar una prenda que fue pagada, se lo informaremos y le devolveremos el valor pagado por el mismo medio de pago.`],
      },
      {
        h: "10. Propiedad intelectual",
        p: [`El nombre y el logo de ${store}, los textos, las fotografías y el diseño de este sitio pertenecen a su titular o se usan con autorización. No se pueden copiar, reproducir ni usar con fines comerciales sin permiso escrito.`],
      },
      {
        h: "11. Uso adecuado del sitio",
        p: [`Está prohibido usar el sitio para fines ilícitos, intentar acceder sin autorización a sus sistemas, interferir con su funcionamiento o crear pedidos sin intención de pagarlos (por ejemplo, para bloquear inventario). Podemos cancelar pedidos y bloquear accesos que incumplan esta regla.`],
      },
      {
        h: "12. Responsabilidad",
        p: [`Hacemos lo razonable para que el sitio esté disponible y sin errores, pero no garantizamos un funcionamiento ininterrumpido. Nada de lo aquí dicho limita los derechos irrenunciables que la ley reconoce al consumidor.`],
      },
      {
        h: "13. Datos personales",
        p: [`Tratamos sus datos conforme a la Ley 1581 de 2012, tal como se explica en la política de tratamiento de datos personales.`],
      },
      {
        h: "14. Peticiones, quejas y reclamos",
        p: [
          `Puede presentar peticiones, quejas, reclamos o sugerencias en ${mail}, indicando su nombre, el código de pedido (si aplica) y una descripción de lo ocurrido. Responderemos lo antes posible y, en todo caso, dentro de los quince (15) días hábiles siguientes a la recepción de su mensaje.`,
          `Si no está conforme con la respuesta, puede acudir a la Superintendencia de Industria y Comercio (SIC), autoridad de protección al consumidor y de protección de datos personales en Colombia.`,
        ],
      },
      {
        h: "15. Cambios en estos términos",
        p: [`Podemos actualizar estos términos. La versión vigente es la publicada en este sitio, con su fecha de actualización, y se aplica a las compras realizadas a partir de ese momento.`],
      },
      {
        h: "16. Ley aplicable",
        p: [`Estos términos se rigen por las leyes de la República de Colombia. Cualquier controversia se resolverá ante las autoridades competentes de Colombia.`],
      },
    ],
  };

  const cambios: Policy = {
    slug: "cambios",
    title: "Cambios y devoluciones",
    summary: "Retracto, garantía, productos con novedades y reversión del pago.",
    sections: [
      {
        h: "1. Derecho de retracto",
        p: [
          `Como la compra se realiza a distancia (en línea), usted puede retractarse de ella sin dar explicaciones, conforme al artículo 47 de la Ley 1480 de 2011.`,
        ],
        ul: [
          `Plazo: cinco (5) días hábiles contados desde la entrega de la prenda.`,
          `Cómo ejercerlo: escriba a ${mail} con su nombre y el código del pedido, indicando que desea retractarse.`,
          `Estado de la prenda: debe devolverse en las mismas condiciones en que se recibió, sin uso, con sus etiquetas y empaque.`,
          `Costos: el transporte de la devolución y los demás gastos que ella implique están a cargo de quien ejerce el retracto (art. 47 de la Ley 1480).`,
          `Reembolso: devolvemos el dinero pagado, por el mismo medio de pago, dentro de los treinta (30) días calendario siguientes a que ejerza el derecho, una vez recibida la prenda.`,
          `Se aplican las excepciones que la propia ley establece para este derecho.`,
        ],
      },
      {
        h: "2. Garantía legal",
        p: [
          `Las prendas tienen la garantía legal que establece la Ley 1480 de 2011 frente a defectos de calidad o idoneidad.`,
          `Si su chaqueta presenta un defecto, escriba a ${mail} con el código del pedido, una descripción del problema y fotografías. Evaluaremos el caso y, según corresponda conforme a la ley, repararemos la prenda, la cambiaremos o devolveremos el dinero.`,
          `La garantía no cubre daños causados por uso indebido, cuidado inadecuado, accidentes o desgaste normal.`,
        ],
      },
      {
        h: "3. Prenda equivocada o con daños de transporte",
        p: [`Si recibe una prenda distinta a la que pidió o con daños que no corresponden al uso, escríbanos tan pronto lo detecte, con el código del pedido y fotografías del producto y del empaque. Le ofreceremos la solución que corresponda según la ley.`],
      },
      {
        h: "4. Cambios de talla o de modelo",
        p: [`El cambio de talla o de modelo no es un derecho legal. Si necesita uno, escríbanos a ${mail} y evaluaremos su solicitud según la disponibilidad y el estado de la prenda.`],
      },
      {
        h: "5. Reversión del pago",
        p: [
          `Si pagó con tarjeta u otro medio electrónico y se presentó un fraude, una operación no solicitada o que no recibió el producto, o este llegó no conforme o defectuoso, puede solicitar la reversión del pago según el artículo 51 de la Ley 1480 de 2011 y el Decreto 587 de 2016.`,
          `Para ello debe presentar su reclamación ante nosotros y ante el emisor de su medio de pago dentro de los cinco (5) días hábiles siguientes a la fecha en que tuvo conocimiento del hecho. Le recomendamos escribirnos primero a ${mail}: en la mayoría de los casos podemos resolverlo directamente.`,
        ],
      },
      {
        h: "6. Autoridad de protección al consumidor",
        p: [`Si considera que sus derechos no fueron atendidos, puede acudir a la Superintendencia de Industria y Comercio (SIC).`],
      },
    ],
  };

  const envios: Policy = {
    slug: "envios",
    title: "Política de envíos",
    summary: "Cobertura, costos y tiempos de entrega.",
    sections: [
      { h: "1. Cobertura", p: [`Realizamos envíos a direcciones dentro de Colombia. No hacemos envíos al exterior.`] },
      {
        h: "2. Costo",
        p: [`El envío cuesta ${fee} por pedido y es gratis cuando el pedido incluye ${free} o más prendas. El valor exacto se muestra en el carrito y en el resumen antes de pagar.`],
      },
      {
        h: "3. Tiempo de entrega",
        p: [`Nuestro tiempo de entrega es de ${days} días hábiles, contados desde que se confirma el pago. Los sábados, domingos y festivos no cuentan como días hábiles.`],
      },
      {
        h: "4. Datos de entrega",
        p: [`Usted debe indicar una dirección completa y un teléfono de contacto vigentes. Si la dirección es incorrecta o no es posible contactarle, la entrega puede demorarse y podría generar costos adicionales de reenvío.`],
      },
      {
        h: "5. Recepción del pedido",
        p: [`Al recibir el paquete, revise que el empaque esté en buen estado. Si encuentra novedades, escríbanos a ${mail} con el código del pedido y fotografías.`],
      },
      {
        h: "6. Seguimiento",
        p: [`Puede consultar el estado de su pedido con su código en la página del pedido, o escribirnos a ${mail}.`],
      },
      {
        h: "7. Demoras por causas ajenas",
        p: [`Las entregas pueden retrasarse por causas fuera de nuestro control (fuerza mayor, bloqueos de vías, condiciones climáticas, novedades de la transportadora). Le informaremos si esto ocurre.`],
      },
    ],
  };

  const datos: Policy = {
    slug: "datos",
    title: "Tratamiento de datos personales",
    summary: "Qué datos recogemos, para qué los usamos y cómo ejercer sus derechos (Ley 1581 de 2012).",
    sections: [
      {
        h: "1. Responsable del tratamiento",
        p: [
          `El responsable del tratamiento de sus datos personales es ${who}. Canal para consultas y reclamos: ${mail}.`,
          `Esta política se expide en cumplimiento de la Ley 1581 de 2012, el Decreto 1377 de 2013 (compilado en el Decreto 1074 de 2015) y demás normas que los complementen.`,
        ],
      },
      {
        h: "2. Datos que recogemos",
        ul: [
          `Datos de identificación y contacto: nombre, correo electrónico y teléfono.`,
          `Datos de entrega: departamento, ciudad, dirección y las notas que usted agregue al pedido.`,
          `Datos del pedido: prendas, tallas, valores y estado del pago.`,
          `Datos técnicos mínimos: la dirección IP, que usamos de forma temporal para la seguridad del sitio (por ejemplo, limitar intentos abusivos).`,
        ],
        p: [
          `No recogemos datos sensibles. Los datos de su tarjeta o cuenta bancaria no pasan por nuestros sistemas: los procesa directamente el proveedor de pagos.`,
          `El sitio no está dirigido a menores de edad.`,
        ],
      },
      {
        h: "3. Para qué usamos sus datos",
        ul: [
          `Procesar y entregar su pedido, y confirmar el pago.`,
          `Enviarle comunicaciones sobre su pedido (confirmación, novedades de entrega).`,
          `Atender consultas, garantías, retractos y reclamos.`,
          `Cumplir obligaciones legales, contables y tributarias.`,
          `Mantener la seguridad del sitio y prevenir fraudes y abusos.`,
        ],
        p: [`No le enviaremos publicidad ni usaremos sus datos para fines de mercadeo sin su autorización previa, expresa e informada.`],
      },
      {
        h: "4. Autorización",
        p: [`Al realizar una compra y marcar la casilla de aceptación en el pago, usted autoriza de manera previa, expresa e informada el tratamiento de sus datos para las finalidades descritas. Puede revocar la autorización o solicitar la supresión de sus datos cuando no exista un deber legal o contractual de conservarlos.`],
      },
      {
        h: "5. Con quién compartimos sus datos",
        p: [`Solo compartimos los datos necesarios con terceros que nos prestan servicios para operar la tienda, que los tratan siguiendo nuestras instrucciones:`],
        ul: [
          `Proveedores de infraestructura y alojamiento del sitio y de la base de datos.`,
          `El proveedor de pagos que procesa su pago.`,
          `El proveedor de envío de correos electrónicos.`,
          `Las empresas de mensajería que entregan su pedido.`,
          `Autoridades, cuando una norma o una orden lo exija.`,
        ],
      },
      {
        h: "6. Transferencia y transmisión internacional",
        p: [`Algunos de estos proveedores tienen servidores fuera de Colombia (por ejemplo, en Estados Unidos). Al aceptar esta política usted autoriza esta transmisión, que realizamos con proveedores que aplican medidas de seguridad adecuadas.`],
      },
      {
        h: "7. Sus derechos",
        p: [`Como titular de los datos usted puede, en cualquier momento y de forma gratuita:`],
        ul: [
          `Conocer, actualizar y rectificar sus datos personales.`,
          `Solicitar prueba de la autorización otorgada.`,
          `Ser informado del uso que se ha dado a sus datos.`,
          `Presentar quejas ante la Superintendencia de Industria y Comercio por infracciones a la ley.`,
          `Revocar la autorización y solicitar la supresión de sus datos, cuando proceda.`,
          `Acceder a sus datos personales que hayan sido objeto de tratamiento.`,
        ],
      },
      {
        h: "8. Cómo ejercer sus derechos",
        p: [
          `Escriba a ${mail} con su nombre completo, un medio de contacto, el código de pedido (si lo tiene) y la descripción de su solicitud. Podemos pedirle información para verificar su identidad.`,
          `Las consultas se responden en un máximo de diez (10) días hábiles, prorrogables por cinco (5) días hábiles más si se le informa el motivo. Los reclamos (corrección, actualización, supresión o revocatoria) se atienden en un máximo de quince (15) días hábiles, prorrogables por ocho (8) días hábiles más si se le informa el motivo.`,
        ],
      },
      {
        h: "9. Seguridad",
        p: [`Aplicamos medidas razonables para proteger sus datos: conexión cifrada (HTTPS), acceso restringido a la información de pedidos, contraseñas de administración almacenadas con hash y registro limitado de actividad. Ningún sistema es infalible; si ocurre un incidente que afecte sus datos, actuaremos conforme a la ley.`],
      },
      {
        h: "10. Conservación",
        p: [`Conservamos sus datos mientras sean necesarios para las finalidades descritas y durante los plazos que exijan las normas contables, tributarias y de protección al consumidor. Luego los suprimimos o anonimizamos.`],
      },
      {
        h: "11. Cookies",
        p: [`Usamos únicamente cookies esenciales para el funcionamiento del sitio: una para recordar el contenido de su carrito (hasta 14 días) y otra de sesión que solo usa el administrador del sitio. No usamos cookies de publicidad ni de analítica de terceros.`],
      },
      {
        h: "12. Cambios en esta política",
        p: [`Si cambiamos esta política de forma sustancial, lo informaremos en este sitio. La versión vigente es la publicada aquí, con su fecha de actualización.`],
      },
    ],
  };

  return { terminos, cambios, envios, datos };
}
