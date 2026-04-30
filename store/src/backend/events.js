/**
 * Wix Events — WECARE.DIGITAL
 *
 * Auto-triggered backend event handlers.
 *
 * Events:
 *   - wixStores_onProductCreated: Auto-assign SKU to new products
 *   - wixEcom_onOrderApproved: Generate custom order ID (WD-ORD prefix)
 *
 * IMPORTANT: events.js does NOT support dynamic exports or
 * webMethod() imports. That's why we import from orderId-helpers.js
 * (plain .js) instead of orderId.web.js.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-stores-backend/events
 */

import wixStoresBackend from 'wix-stores-backend';
import wixData from 'wix-data';
import { getSecret } from 'wix-secrets-backend';
import { createOrGetOrderId } from 'backend/orderId-helpers';

const CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const SKU_LENGTH = 8;
const MAX_COLLISION_RETRIES = 10;

function makeRandomSku ()
{
  let sku = "";
  for ( let i = 0; i < SKU_LENGTH; i++ )
  {
    const index = Math.floor( Math.random() * CHARSET.length );
    sku += CHARSET.charAt( index );
  }
  return sku;
}

async function getExistingSkus ()
{
  const skus = new Set();
  let result = await wixData.query( "Stores/Products" ).limit( 100 ).find();
  result.items.forEach( p =>
  {
    if ( p.sku ) skus.add( p.sku.trim().toUpperCase() );
  } );
  while ( result.hasNext() )
  {
    result = await result.next();
    result.items.forEach( p =>
    {
      if ( p.sku ) skus.add( p.sku.trim().toUpperCase() );
    } );
  }
  return skus;
}

function makeUniqueSku ( existingSkus )
{
  let attempts = 0;
  let sku;
  do
  {
    sku = makeRandomSku();
    attempts++;
    if ( attempts > MAX_COLLISION_RETRIES )
    {
      console.error( `[events] Failed to generate unique SKU after ${ MAX_COLLISION_RETRIES } attempts` );
      return sku;
    }
  } while ( existingSkus.has( sku.toUpperCase() ) );
  existingSkus.add( sku.toUpperCase() );
  return sku;
}

async function updateVariantSkusForProduct ( productId, productSku )
{
  try
  {
    const product = await wixData.get( "Stores/Products", productId );
    if ( !product.manageVariants ) return;

    const variantsResult = await wixData
      .query( "Stores/Variants" )
      .eq( "productId", productId )
      .limit( 100 )
      .find();

    if ( !variantsResult.items.length ) return;

    const variantData = [];
    let index = 1;
    for ( const variant of variantsResult.items )
    {
      const choices = variant.choices;
      const variantSku = productSku + "-" + String( index ).padStart( 2, "0" );
      variantData.push( { sku: variantSku, choices } );
      index++;
    }

    if ( variantData.length )
    {
      await wixStoresBackend.updateVariantData( productId, variantData );
      console.log( `[events] Set ${ variantData.length } variant SKUs for product ${ productId }` );
    }
  } catch ( err )
  {
    console.error( `[events] Failed to update variant SKUs for product ${ productId }:`, err?.message || err );
  }
}

/**
 * Runs automatically whenever a new product is created in Wix Stores.
 */
export async function wixStores_onProductCreated ( event )
{
  const productId = event._id;
  try
  {
    const existingSkus = await getExistingSkus();
    const productSku = makeUniqueSku( existingSkus );
    await wixStoresBackend.updateProductFields( productId, { sku: productSku } );
    console.log( `[events] Assigned SKU ${ productSku } to new product ${ productId }` );
    await updateVariantSkusForProduct( productId, productSku );
  } catch ( err )
  {
    console.error( `[events] Failed to assign SKU for product ${ productId }:`, err?.message || err );
  }
}

/**
 * Triggered when a new order is approved (paid).
 * Generates WD-ORD number and stores in OrderIDs + OrderCustomIds.
 * Also sets the Wix order customField so it shows in Owner App.
 * 
 * NEW: Sends order confirmation via:
 * 1. WhatsApp — wd_order template via WABA1 (+919330994400)
 * 2. SMS — Airtel IQ (WDBEEP header, DLT template 1007723091207562020)
 * 3. Logs delivery status to OrderNotifications collection
 */
export async function wixEcom_onOrderApproved ( event )
{
  const order = event.entity || event;
  const orderId = order._id || order.orderId;
  if ( !orderId ) return;

  const buyer = order.buyerInfo || {};
  const orderDate = order._createdDate || order._dateCreated || new Date();

  let wdOrderId = '';
  try
  {
    wdOrderId = await createOrGetOrderId( {
      wixOrderId: orderId,
      memberId: buyer.memberId || buyer.visitorId || '',
      orderNumber: order.number ? String( order.number ) : '',
      buyerEmail: buyer.email || '',
      buyerPhone: buyer.phone || '',
      totalAmount: '',
      currency: order.currency || '',
      productsSummary: '',
      orderDate,
    } );

    console.log( `[events] Order ${ orderId } → ${ wdOrderId }` );

    // Set customField on the order so WD number shows in Wix Owner App
    try
    {
      const orderRecord = await wixData.get( 'Stores/Orders', orderId, { suppressAuth: true } );
      if ( orderRecord )
      {
        await wixData.update( 'Stores/Orders', {
          ...orderRecord,
          customField: { title: 'Order ID', value: wdOrderId },
        }, { suppressAuth: true } );
        console.log( `[events] Set customField on order ${ orderId } → ${ wdOrderId }` );
      }
    } catch ( cfErr )
    {
      console.error( `[events] Failed to set customField on order ${ orderId }:`, cfErr?.message );
    }
  } catch ( err )
  {
    console.error( `[events] Failed to assign WD order number to order ${ orderId }:`, err?.message || err );
  }

  // ── Send order confirmation notifications ──
  const buyerPhone = buyer.phone || '';
  if ( buyerPhone )
  {
    sendOrderNotifications( orderId, wdOrderId, buyerPhone, buyer.email || '' ).catch( err =>
    {
      console.error( `[events] Notification error for order ${ orderId }:`, err?.message || err );
    } );
  } else
  {
    console.log( `[events] No buyer phone for order ${ orderId }, skipping notifications` );
  }
}

/**
 * Send WhatsApp + SMS order confirmation.
 * Hardcoded to WABA1 +919330994400 for WhatsApp.
 * Uses Airtel IQ for SMS (DLT template 1007723091207562020, header WDBEEP).
 * Logs delivery status to OrderNotifications collection.
 */
async function sendOrderNotifications ( orderId, wdOrderId, phone, email )
{
  const STACK_API = 'https://stack.wecare.digital/api';
  let apiKey = '';
  try { apiKey = await getSecret( 'WECARE_API_KEY' ); } catch { }

  const notifRecord = {
    _id: orderId,
    orderId: orderId,
    wdOrderId: wdOrderId || '',
    phone: phone,
    email: email || '',
    whatsappStatus: 'pending',
    whatsappMessageId: '',
    whatsappError: '',
    smsStatus: 'pending',
    smsMessageId: '',
    smsError: '',
    rcsStatus: 'not_available',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  // ── 1. WhatsApp via WABA1 (+919330994400) ──
  try
  {
    const waPayload = {
      phoneNumberId: 'phone-number-id-waba1-direct-1016149501586345',
      to: phone,
      type: 'template',
      template: {
        name: 'wd_order',
        language: { code: 'en' },
        components: [
          {
            type: 'header',
            parameters: [
              { type: 'video', video: { link: 'https://app.wecare.digital/stream/media/m/selfservice.mp4' } }
            ]
          }
        ],
      },
    };

    const waResp = await fetch( STACK_API + '/messaging/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...( apiKey ? { 'x-api-key': apiKey } : {} ),
      },
      body: JSON.stringify( waPayload ),
    } );
    const waData = await waResp.json();

    if ( waData.messageId || waData.success )
    {
      notifRecord.whatsappStatus = 'sent';
      notifRecord.whatsappMessageId = waData.messageId || '';
      console.log( `[events] WhatsApp sent for order ${ orderId }: ${ waData.messageId }` );
    } else
    {
      notifRecord.whatsappStatus = 'failed';
      notifRecord.whatsappError = waData.error || JSON.stringify( waData ).substring( 0, 200 );
      console.error( `[events] WhatsApp failed for order ${ orderId }:`, waData.error || waData );
    }
  } catch ( waErr )
  {
    notifRecord.whatsappStatus = 'failed';
    notifRecord.whatsappError = waErr?.message || String( waErr );
    console.error( `[events] WhatsApp error for order ${ orderId }:`, waErr?.message );
  }

  // ── 2. SMS via Airtel IQ (WDBEEP, DLT 1007723091207562020) ──
  try
  {
    const smsContent = 'Thanks for placing your order with WECARE.DIGITAL!\n\n'
      + 'Your order has been received. We\'ll review it and share updates shortly.\n\n'
      + 'Need help? Submit a request here: https://wecare.digital/selfservice '
      + 'or message / voice note us on WhatsApp: https://r.wecare.digital/wa.';

    const smsPayload = {
      phoneNumber: phone,
      content: smsContent,
      provider: 'airtel',
      messageType: 'SERVICE_IMPLICIT',
      dltTemplateId: '1007723091207562020',
      entityId: '1201161991108627443',
      sourceAddress: 'WDBEEP',
      apiVersion: 'v5',
      metaData: { orderId: orderId, wdOrderId: wdOrderId || '' },
    };

    const smsResp = await fetch( STACK_API + '/messaging/sms', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...( apiKey ? { 'x-api-key': apiKey } : {} ),
      },
      body: JSON.stringify( smsPayload ),
    } );
    const smsData = await smsResp.json();

    if ( smsData.messageId || smsData.success )
    {
      notifRecord.smsStatus = 'sent';
      notifRecord.smsMessageId = smsData.messageId || '';
      console.log( `[events] SMS sent for order ${ orderId }: ${ smsData.messageId }` );
    } else
    {
      notifRecord.smsStatus = 'failed';
      notifRecord.smsError = smsData.error || JSON.stringify( smsData ).substring( 0, 200 );
      console.error( `[events] SMS failed for order ${ orderId }:`, smsData.error || smsData );
    }
  } catch ( smsErr )
  {
    notifRecord.smsStatus = 'failed';
    notifRecord.smsError = smsErr?.message || String( smsErr );
    console.error( `[events] SMS error for order ${ orderId }:`, smsErr?.message );
  }

  // ── 3. RCS via Sinch (if enabled — calls stack API) ──
  try
  {
    const rcsPayload = {
      phoneNumber: phone,
      channel: 'RCS',
      notificationType: 'order_confirmation',
      orderId: orderId,
      wdOrderId: wdOrderId || '',
    };

    const rcsResp = await fetch( STACK_API + '/rcs/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...( apiKey ? { 'x-api-key': apiKey } : {} ),
      },
      body: JSON.stringify( rcsPayload ),
    } );
    const rcsData = await rcsResp.json();

    if ( rcsData.success || rcsData.messageId )
    {
      notifRecord.rcsStatus = 'sent';
      notifRecord.rcsMessageId = rcsData.messageId || rcsData.message_id || '';
      console.log( `[events] RCS sent for order ${ orderId }: ${ notifRecord.rcsMessageId }` );
    } else
    {
      notifRecord.rcsStatus = rcsData.error === 'RCS not enabled' ? 'not_available' : 'failed';
      notifRecord.rcsError = rcsData.error || '';
    }
  } catch ( rcsErr )
  {
    notifRecord.rcsStatus = 'failed';
    notifRecord.rcsError = rcsErr?.message || String( rcsErr );
    console.error( `[events] RCS error for order ${ orderId }:`, rcsErr?.message );
  }

  // ── 4. Log to OrderNotifications collection ──
  notifRecord.updatedAt = new Date();
  try
  {
    await wixData.insert( 'OrderNotifications', notifRecord, { suppressAuth: true } );
    console.log( `[events] Notification log saved for order ${ orderId }` );
  } catch ( logErr )
  {
    // Try update if insert fails (duplicate key)
    try
    {
      await wixData.update( 'OrderNotifications', notifRecord, { suppressAuth: true } );
    } catch { }
    console.error( `[events] Failed to log notification for order ${ orderId }:`, logErr?.message );
  }
}
