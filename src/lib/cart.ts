/**
 * The browser shopping cart for /shop/ - references and quantities only.
 *
 * THE ONE RULE THIS FILE EXISTS TO ENFORCE: the browser never sends a price, an amount, a
 * currency or any financial figure to the checkout. A cart entry carries a catalogue REFERENCE
 * (the product's Wix catalogue id, with its slug and name for display) and a QUANTITY, and nothing
 * else reaches the server. The amount charged is decided server-side from a live Wix checkout read
 * and compared in integer paise (amplify/functions/ecommerce/checkout/handler.py rule 2), so a
 * number invented here could only ever be wrong or dangerous. `formattedPrice` is kept for the
 * cart LIST rendering only - it is Wix's own passthrough string, never rebuilt, and it is stripped
 * out entirely by toLineItems(): see the test that asserts the serialized payload has no
 * price-like key.
 *
 * WHY LOCALSTORAGE. The cart must survive the sign-in/register redirect (a public shopper who
 * proceeds is bounced to the OTP step and back), so it cannot live in component state. It is not
 * sensitive - it is a list of catalogue references a visitor chose - so localStorage is the right
 * store; the session token stays in sessionStorage (customerAuth.ts) where it belongs. Every
 * window/storage access is SSR-guarded (typeof window === 'undefined'), matching customerAuth.ts,
 * because these pages are statically exported and this module is imported into prerendered code.
 *
 * THE lineItems SHAPE MATCHES THE BACKEND CONTRACT. wix_ecom.create_checkout documents its input
 * as `{catalogReference, quantity}` entries - "a reference into the Wix catalogue, never a price".
 * The products are dummy placeholders today, so the exact nested Wix catalogReference object
 * (catalogItemId/appId) is not knowable from this repo; toLineItems() therefore sends the
 * product's Wix catalogue id as the catalogReference and the quantity, which is refs+quantities
 * ONLY and is trivially remapped to the final nested shape once real products are chosen. See the
 * findings note on the assumption.
 */

import type { ShopProduct } from '../content/shop';

/** localStorage key. Namespaced and versioned so a shape change can be migrated, not guessed. */
const CART_KEY = 'wecare.cart.v1';

/**
 * Fired on `window` after every write, so the header's Shopping Bag badge can re-read the count.
 *
 * The browser's own `storage` event is not enough on its own: it fires in OTHER tabs and never in
 * the one that made the write, so adding an item on /shop/<slug>/ would leave the badge in the
 * same document stale until the next navigation. The header listens for both.
 */
export const CART_CHANGED_EVENT = 'wecare:cart-changed';

export interface CartItem {
  productId?: string;
  variantId?: string;
  /** The catalogue reference: the product's Wix catalogue id. Never a price. */
  ref: string;
  /** The product slug, so the cart can link back to /shop/<slug>/. */
  slug: string;
  /** Display name for the cart list. */
  name: string;
  /** Wix's own formatted price string, e.g. "₹6,999.00". DISPLAY ONLY - never sent to the server. */
  formattedPrice: string;
  /** How many, always a positive integer. */
  quantity: number;
}

/** One entry of the checkout `create` payload: a catalogue reference and a quantity, nothing else. */
export interface CheckoutLineItem {
  catalogReference: { appId: string; catalogItemId: string; options?: { variantId: string } };
  quantity: number;
}

/** True when there is a browser to read storage from. Mirrors customerAuth.ts's SSR guard. */
function hasWindow (): boolean {
  return typeof window !== 'undefined';
}

/** A quantity coerced to a positive integer; anything invalid becomes 1. */
function normaliseQuantity ( value: unknown ): number {
  const n = Math.floor( Number( value ) );
  return Number.isFinite( n ) && n > 0 ? n : 1;
}

/** Parse and validate whatever is in storage into a clean CartItem[]. Never throws. */
function parseCart ( raw: string | null ): CartItem[] {
  if ( !raw ) return [];
  let parsed: unknown;
  try
  {
    parsed = JSON.parse( raw );
  }
  catch
  {
    return [];
  }
  if ( !Array.isArray( parsed ) ) return [];
  const out: CartItem[] = [];
  for ( const entry of parsed )
  {
    const item = entry as Partial<CartItem>;
    const ref = String( item?.ref || '' );
    if ( !ref ) continue;
    out.push( {
      ref,
      ...( item.productId ? { productId: String( item.productId ) } : {} ),
      ...( item.variantId ? { variantId: String( item.variantId ) } : {} ),
      slug: String( item?.slug || '' ),
      name: String( item?.name || '' ),
      formattedPrice: String( item?.formattedPrice || '' ),
      quantity: normaliseQuantity( item?.quantity ),
    } );
  }
  return out;
}

/** The current cart, or [] on the server / when storage is empty or corrupt. */
export function readCart (): CartItem[] {
  if ( !hasWindow() ) return [];
  return parseCart( window.localStorage.getItem( CART_KEY ) );
}

/** Persist the cart. No-op on the server. */
function writeCart ( items: CartItem[] ): void {
  if ( !hasWindow() ) return;
  window.localStorage.setItem( CART_KEY, JSON.stringify( items ) );
  announce();
}

/**
 * Tell this document the cart moved. Guarded on CustomEvent as well as window, because the SSR
 * guard above only proves there is a window - and jsdom-less environments have neither.
 */
function announce (): void {
  if ( !hasWindow() || typeof window.CustomEvent !== 'function' ) return;
  window.dispatchEvent( new window.CustomEvent( CART_CHANGED_EVENT ) );
}

/**
 * Add a product to the cart, or increase its quantity if it is already there. Keyed on the
 * product's catalogue id (its stable reference), not its name, so a renamed product still merges.
 * Returns the updated cart.
 */
export function addItem ( product: ShopProduct, qty = 1, selectedVariantId?: string ): CartItem[] {
  const variantId = selectedVariantId || ( product.variants?.length === 1 ? product.variants[0].id : undefined );
  if ( product.variants && product.variants.length > 1 && !variantId ) throw new Error( 'Choose an option first.' );
  if ( variantId && !product.variants?.some( variant => variant.id === variantId && variant.inStock ) ) throw new Error( 'Choose an available option.' );
  const ref = String( product.id || product.slug || '' ) + ( variantId ? `:${variantId}` : '' );
  if ( !ref ) return readCart();
  const quantity = normaliseQuantity( qty );
  const items = readCart();
  const existing = items.find( item => item.ref === ref );
  if ( existing )
  {
    existing.quantity += quantity;
  }
  else
  {
    items.push( {
      productId: product.id,
      ...( variantId ? { variantId } : {} ),
      ref,
      slug: String( product.slug || '' ),
      name: String( product.name || '' ),
      formattedPrice: String( product.formattedPrice || '' ),
      quantity,
    } );
  }
  writeCart( items );
  return items;
}

/**
 * Set the exact quantity for a reference. A quantity of zero or below removes the line, so the
 * quantity control can reach "gone" without a separate button. Returns the updated cart.
 */
export function setQuantity ( ref: string, qty: number ): CartItem[] {
  const items = readCart();
  const next = Math.floor( Number( qty ) );
  if ( !Number.isFinite( next ) || next <= 0 )
  {
    return removeItem( ref );
  }
  const existing = items.find( item => item.ref === ref );
  if ( existing ) existing.quantity = next;
  writeCart( items );
  return items;
}

/** Remove a line by reference. Returns the updated cart. */
export function removeItem ( ref: string ): CartItem[] {
  const items = readCart().filter( item => item.ref !== ref );
  writeCart( items );
  return items;
}

/** Empty the cart. Called after a checkout is successfully prepared. */
export function clearCart (): void {
  if ( !hasWindow() ) return;
  window.localStorage.removeItem( CART_KEY );
  announce();
}

/** Total number of units across all lines - for a header badge or an empty check. */
export function cartCount (): number {
  return readCart().reduce( ( sum, item ) => sum + item.quantity, 0 );
}

/**
 * The checkout `create` payload: catalogue references and quantities ONLY.
 *
 * This is the boundary the whole design rests on. Every returned entry is exactly
 * `{ catalogReference, quantity }` - no price, no amount, no currency, no formattedPrice. A test
 * asserts the serialized JSON of this output contains no price-like key. `catalogReference` is the
 * product's Wix catalogue id (see the module docblock and findings for the dummy-product
 * assumption); the server reads the authoritative total from a live Wix checkout, not from this.
 */
export function toLineItems ( items: CartItem[] = readCart() ): CheckoutLineItem[] {
  return items
    .filter( item => item.ref && item.quantity > 0 )
    .map( item => ( { catalogReference: { appId: '215238eb-22a5-4c36-9e7b-e7c08025e04e', catalogItemId: item.productId || item.ref, ...( item.variantId ? { options: { variantId: item.variantId } } : {} ) }, quantity: item.quantity } ) );
}
