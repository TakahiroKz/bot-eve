/**
 * Interfaz de pagos. La pasarela real (Wompi, Mercado Pago o PayU) se define más adelante: se añade un
 * proveedor nuevo aquí sin tocar el checkout. Un pedido pasa a «pagado» SOLO por `confirmPayment`,
 * llamado desde el webhook verificado del proveedor.
 */
export interface PaymentProvider {
  name: string;
  /** Devuelve la URL a la que se envía al cliente para pagar. */
  start(order: { code: string; total: number; email: string }): Promise<{ redirectUrl: string }>;
}

const simulated: PaymentProvider = {
  name: "simulated",
  async start(order) {
    return { redirectUrl: `/pago/simulado/${order.code}` };
  },
};

export function getProvider(): PaymentProvider {
  const name = process.env.PAYMENTS_PROVIDER ?? "simulated";
  if (name === "simulated") {
    if (process.env.NODE_ENV === "production") {
      throw new Error("El proveedor de pagos simulado no puede usarse en producción");
    }
    return simulated;
  }
  throw new Error(`Proveedor de pagos desconocido: ${name} (pendiente de implementar)`);
}
