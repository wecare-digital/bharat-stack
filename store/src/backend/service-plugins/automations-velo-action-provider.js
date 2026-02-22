/**
 * Automations Velo Action Provider — WECARE.DIGITAL
 *
 * Custom automation actions for Wix Automations.
 * These actions can be used in Wix Automations workflows
 * to trigger custom logic when automation rules fire.
 *
 * Actions:
 *   - sendWhatsAppNotification: Send order notification via WhatsApp
 *   - assignCustomOrderId: Generate WD order number
 *   - syncOrderToAWS: Push order data to AWS backend
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-automations/service-provider
 */

import { getSecret } from 'wix-secrets-backend';
// native fetch() is available globally — wix-fetch is deprecated
import wixData from 'wix-data';
import { createOrGetOrderId } from 'backend/orderId-helpers';

/**
 * Provide the list of available automation actions.
 * Called by Wix Automations to discover custom actions.
 */
export function getActions() {
  return {
    actions: [
      {
        id: 'send-whatsapp-notification',
        name: 'Send WhatsApp Order Notification',
        description: 'Send an order confirmation or update via WhatsApp through WECARE.DIGITAL',
        inputSchema: {
          type: 'object',
          properties: {
            orderId: { type: 'string', title: 'Order ID' },
            phone: { type: 'string', title: 'Customer Phone' },
            templateName: { type: 'string', title: 'Template Name', default: 'order_confirmation' },
          },
          required: ['orderId', 'phone'],
        },
      },
      {
        id: 'assign-custom-order-id',
        name: 'Assign Custom Order ID',
        description: 'Generate a WD-ORD-prefixed custom order number',
        inputSchema: {
          type: 'object',
          properties: {
            orderId: { type: 'string', title: 'Order ID' },
          },
          required: ['orderId'],
        },
      },
      {
        id: 'sync-order-to-aws',
        name: 'Sync Order to AWS',
        description: 'Push order data to WECARE.DIGITAL AWS backend for processing',
        inputSchema: {
          type: 'object',
          properties: {
            orderId: { type: 'string', title: 'Order ID' },
          },
          required: ['orderId'],
        },
      },
    ],
  };
}

/**
 * Execute an automation action.
 * Called by Wix Automations when a rule triggers one of our actions.
 */
export async function executeAction({ actionId, input }) {
  switch (actionId) {
    case 'send-whatsapp-notification':
      return await handleWhatsAppNotification(input);
    case 'assign-custom-order-id':
      return await handleAssignCustomOrderId(input);
    case 'sync-order-to-aws':
      return await handleSyncOrderToAWS(input);
    default:
      return { success: false, error: `Unknown action: ${actionId}` };
  }
}

// ---------------------------------------------------------------------------
// Action handlers
// ---------------------------------------------------------------------------

async function handleWhatsAppNotification({ orderId, phone, templateName = 'order_confirmation' }) {
  try {
    const apiUrl = await getSecret('WECARE_API_URL');
    if (!apiUrl) throw new Error('WECARE_API_URL secret not configured');

    const response = await fetch(`${apiUrl}/whatsapp/send-template`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone,
        templateName,
        params: { orderId },
        source: 'wix-automation',
      }),
    });

    const result = await response.json();
    return { success: response.ok, ...result };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function handleAssignCustomOrderId({ orderId }) {
  try {
    const wdOrderId = await createOrGetOrderId({ wixOrderId: orderId });
    return {
      success: true,
      customOrderNumber: wdOrderId,
    };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function handleSyncOrderToAWS({ orderId }) {
  try {
    const apiUrl = await getSecret('WECARE_API_URL');
    if (!apiUrl) throw new Error('WECARE_API_URL secret not configured');

    // Fetch order from Wix Data
    const order = await wixData.get('Stores/Orders', orderId, { suppressAuth: true });
    if (!order) throw new Error(`Order ${orderId} not found`);

    const response = await fetch(`${apiUrl}/wix-store/sync/order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order }),
    });

    const result = await response.json();
    return { success: response.ok, ...result };
  } catch (err) {
    return { success: false, error: err.message };
  }
}
