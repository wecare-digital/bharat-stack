/**
 * Product Manager — WECARE.DIGITAL Store (Velo Web Module)
 *
 * Create, update, and manage products in the Wix Store via Velo.
 * Called from the CRM dashboard (stack.wecare.digital/store) through
 * the Lambda → Velo HTTP Functions pipeline.
 *
 * Uses wix-stores-backend for product CRUD operations.
 * Ref: https://dev.wix.com/docs/velo/apis/wix-stores-backend
 *
 * Category: BNB CLUB (Visa Assistance, Travel, Concierge)
 */

import { Permissions, webMethod } from 'wix-web-module';
import wixStoresBackend from 'wix-stores-backend';
import wixData from 'wix-data';

// ---------------------------------------------------------------------------
// Create a single product
// ---------------------------------------------------------------------------
export const createProduct = webMethod(
  Permissions.Admin,
  async (productData) => {
    try {
      // Ensure all products are in stock by default
      if (!productData.stock) {
        productData.stock = { inStock: true, trackInventory: false, inventoryStatus: 'IN_STOCK' };
      }
      const product = await wixStoresBackend.createProduct(productData);
      return { success: true, product };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }
);

// ---------------------------------------------------------------------------
// Update an existing product
// ---------------------------------------------------------------------------
export const updateProduct = webMethod(
  Permissions.Admin,
  async (productId, updates) => {
    try {
      const product = await wixStoresBackend.updateProductFields(productId, updates);
      return { success: true, product };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }
);

// ---------------------------------------------------------------------------
// Bulk create products (array of product data objects)
// ---------------------------------------------------------------------------
export const bulkCreateProducts = webMethod(
  Permissions.Admin,
  async (productsArray) => {
    const results = [];
    for (const productData of productsArray) {
      try {
        const product = await wixStoresBackend.createProduct(productData);
        results.push({ success: true, name: productData.name, productId: product._id });
      } catch (err) {
        results.push({ success: false, name: productData.name, error: err.message });
      }
    }
    return {
      total: productsArray.length,
      succeeded: results.filter(r => r.success).length,
      failed: results.filter(r => !r.success).length,
      results,
    };
  }
);

// ---------------------------------------------------------------------------
// Delete a product
// ---------------------------------------------------------------------------
export const deleteProduct = webMethod(
  Permissions.Admin,
  async (productId) => {
    try {
      await wixStoresBackend.deleteProduct(productId);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }
);

// ---------------------------------------------------------------------------
// Add product to a collection
// ---------------------------------------------------------------------------
export const addToCollection = webMethod(
  Permissions.Admin,
  async (productId, collectionId) => {
    try {
      await wixStoresBackend.addProductsToCollection(collectionId, [productId]);
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }
);

// ---------------------------------------------------------------------------
// Sample product templates — BNB CLUB category
// Description = tagline only. Detailed info in additionalInfoSections.
// SKU is NOT set here — events.js auto-generates WD-XX-XXXX on creation.
// ---------------------------------------------------------------------------
export const getSampleProducts = webMethod(
  Permissions.Anyone,
  async () => {
    return {
      category: 'BNB CLUB',
      products: [
        {
          name: 'Visa Assistance — Tourist Visa (Single Country)',
          productType: 'physical',
          description: '<p><strong>End-to-end visa application support for a single destination.</strong></p>',
          weight: 0,
          ribbon: 'BNB CLUB',
          brand: 'WECARE.DIGITAL',
          manageVariants: false,
          priceData: { currency: 'INR', price: 2999 },
          costAndProfitData: { itemCost: 0 },
          customTextFields: [
            { title: 'Destination Country', maxLength: 100, mandatory: true },
            { title: 'Passport Number', maxLength: 20, mandatory: true },
            { title: 'Travel Date (approx)', maxLength: 30, mandatory: true },
          ],
          additionalInfoSections: [
            {
              title: 'Overview',
              description: `<p><strong>WECARE.DIGITAL BNB CLUB — Visa Assistance</strong></p>
<p>Our dedicated visa specialists handle everything from document preparation to appointment scheduling for a single destination country.</p>`,
            },
            {
              title: "What's Included",
              description: `<ul>
<li>Document checklist tailored to your destination & nationality</li>
<li>Application form filling & review</li>
<li>Appointment booking at VFS / Embassy</li>
<li>Cover letter & travel itinerary preparation</li>
<li>Pre-submission document audit</li>
<li>Real-time status tracking via WhatsApp</li>
<li>Post-approval travel advisory</li>
</ul>
<p><strong>Processing Time</strong><br/>Standard: 7–15 business days (varies by country)<br/>Express: 3–5 business days (where available, additional charges apply)</p>`,
            },
            {
              title: 'Requirements',
              description: `<ul>
<li>Valid passport (min 6 months validity)</li>
<li>Passport-size photographs (white background)</li>
<li>Bank statements (last 6 months)</li>
<li>Employment / business proof</li>
<li>Travel insurance (we can arrange)</li>
<li>Hotel booking confirmation</li>
<li>Flight itinerary</li>
</ul>`,
            },
            {
              title: 'Cancellations, Refunds & Shipping',
              description: `<p>Service fee is non-refundable once document processing begins. If visa is rejected, a 50% credit is issued toward your next application. Embassy/VFS fees are non-refundable as per their policy.</p>
<p><strong>Delivery:</strong> Digital delivery via WhatsApp and email. Nothing physical is shipped.</p>`,
            },
            {
              title: 'Contact',
              description: `<p>WhatsApp: +91 93309 94400<br/>Email: visa@wecare.digital<br/>Hours: Mon–Sat, 10 AM – 7 PM IST</p>`,
            },
          ],
        },
        {
          name: 'Visa Assistance — Schengen Multi-Country',
          productType: 'physical',
          description: '<p><strong>Complete Schengen visa service covering all 27 member states.</strong></p>',
          weight: 0,
          ribbon: 'BNB CLUB',
          brand: 'WECARE.DIGITAL',
          manageVariants: false,
          priceData: { currency: 'INR', price: 4999 },
          costAndProfitData: { itemCost: 0 },
          customTextFields: [
            { title: 'Countries to Visit', maxLength: 200, mandatory: true },
            { title: 'Passport Number', maxLength: 20, mandatory: true },
            { title: 'Travel Dates', maxLength: 50, mandatory: true },
          ],
          additionalInfoSections: [
            {
              title: 'Overview',
              description: `<p><strong>WECARE.DIGITAL BNB CLUB — Schengen Visa</strong></p>
<p>Ideal for multi-city European trips. We handle Schengen-specific documentation, VFS appointments, and compliant travel insurance.</p>`,
            },
            {
              title: "What's Included",
              description: `<ul>
<li>Schengen-specific document preparation</li>
<li>Multi-country itinerary planning</li>
<li>VFS appointment booking</li>
<li>Travel insurance arrangement (Schengen-compliant, min €30,000)</li>
<li>Cover letter with detailed travel plan</li>
<li>WhatsApp status updates</li>
</ul>`,
            },
            {
              title: 'Requirements',
              description: `<ul>
<li>Valid passport (min 6 months, 2 blank pages)</li>
<li>Schengen-compliant travel insurance (min €30,000 coverage)</li>
<li>Bank statements (last 6 months, min balance varies)</li>
<li>Employment letter / ITR</li>
<li>Hotel bookings for all countries</li>
<li>Flight itinerary (round trip)</li>
<li>Passport-size photos (35×45mm, white background)</li>
</ul>`,
            },
            {
              title: 'Cancellations, Refunds & Shipping',
              description: `<p>Service fee is non-refundable once document processing begins. If visa is rejected, a 50% credit is issued toward your next application. Embassy/VFS fees are non-refundable as per their policy.</p>
<p><strong>Delivery:</strong> Digital delivery via WhatsApp and email. Nothing physical is shipped.</p>`,
            },
            {
              title: 'Contact',
              description: `<p>WhatsApp: +91 93309 94400<br/>Email: visa@wecare.digital<br/>Hours: Mon–Sat, 10 AM – 7 PM IST</p>`,
            },
          ],
        },
        {
          name: 'Visa Assistance — Business / Conference Visa',
          productType: 'physical',
          description: '<p><strong>Specialized visa support for business travelers and conference attendees.</strong></p>',
          weight: 0,
          ribbon: 'BNB CLUB',
          brand: 'WECARE.DIGITAL',
          manageVariants: false,
          priceData: { currency: 'INR', price: 3999 },
          costAndProfitData: { itemCost: 0 },
          customTextFields: [
            { title: 'Destination Country', maxLength: 100, mandatory: true },
            { title: 'Purpose of Visit', maxLength: 200, mandatory: true },
            { title: 'Company Name', maxLength: 100, mandatory: true },
          ],
          additionalInfoSections: [
            {
              title: 'Overview',
              description: `<p><strong>WECARE.DIGITAL BNB CLUB — Business Visa</strong></p>
<p>Priority support for business travelers, conference attendees, and corporate delegations with express processing where available.</p>`,
            },
            {
              title: "What's Included",
              description: `<ul>
<li>Business invitation letter guidance</li>
<li>Company registration & GST documentation</li>
<li>Conference/event registration support</li>
<li>Priority appointment booking</li>
<li>Express processing (where available)</li>
<li>WhatsApp status updates</li>
</ul>`,
            },
            {
              title: 'Requirements',
              description: `<ul>
<li>Valid passport (min 6 months validity)</li>
<li>Business invitation letter from host company</li>
<li>Company registration / GST certificate</li>
<li>Bank statements (last 6 months)</li>
<li>Conference registration (if applicable)</li>
<li>Passport-size photographs</li>
</ul>`,
            },
            {
              title: 'Cancellations, Refunds & Shipping',
              description: `<p>Service fee is non-refundable once document processing begins. If visa is rejected, a 50% credit is issued toward your next application. Embassy/VFS fees are non-refundable as per their policy.</p>
<p><strong>Delivery:</strong> Digital delivery via WhatsApp and email. Nothing physical is shipped.</p>`,
            },
            {
              title: 'Contact',
              description: `<p>WhatsApp: +91 93309 94400<br/>Email: visa@wecare.digital<br/>Hours: Mon–Sat, 10 AM – 7 PM IST</p>`,
            },
          ],
        },
      ],
    };
  }
);
