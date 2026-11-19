export const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS settings (
  key text PRIMARY KEY,
  value text NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  id serial PRIMARY KEY,
  slug text UNIQUE NOT NULL,
  name text NOT NULL,
  gender text NOT NULL CHECK (gender IN ('hombre','mujer')),
  color text NOT NULL,
  tagline text NOT NULL DEFAULT '',
  description text NOT NULL DEFAULT '',
  price integer NOT NULL CHECK (price >= 0),
  active boolean NOT NULL DEFAULT true,
  position integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS product_images (
  id serial PRIMARY KEY,
  product_id integer NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  url text NOT NULL,
  alt text NOT NULL DEFAULT '',
  position integer NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS variants (
  id serial PRIMARY KEY,
  product_id integer NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  size text NOT NULL,
  stock integer NOT NULL DEFAULT 0 CHECK (stock >= 0),
  UNIQUE (product_id, size)
);
CREATE TABLE IF NOT EXISTS orders (
  id serial PRIMARY KEY,
  code text UNIQUE NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','shipped','delivered','cancelled','expired')),
  customer_name text NOT NULL,
  email text NOT NULL,
  phone text NOT NULL,
  department text NOT NULL,
  city text NOT NULL,
  address text NOT NULL,
  notes text NOT NULL DEFAULT '',
  subtotal integer NOT NULL,
  shipping integer NOT NULL,
  total integer NOT NULL,
  payment_provider text NOT NULL DEFAULT '',
  payment_ref text NOT NULL DEFAULT '',
  reserved_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  paid_at timestamptz,
  confirmation_sent_at timestamptz
);
CREATE TABLE IF NOT EXISTS order_items (
  id serial PRIMARY KEY,
  order_id integer NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  variant_id integer NOT NULL REFERENCES variants(id),
  product_name text NOT NULL,
  size text NOT NULL,
  unit_price integer NOT NULL,
  qty integer NOT NULL CHECK (qty > 0)
);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS confirmation_sent_at timestamptz;
CREATE INDEX IF NOT EXISTS order_items_variant ON order_items(variant_id);
CREATE INDEX IF NOT EXISTS orders_status ON orders(status, reserved_until);
`;
