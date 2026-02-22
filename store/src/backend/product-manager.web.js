/**
 * Product Manager — WECARE.DIGITAL Store (Velo Web Module)
 *
 * Create, update, and manage products in the Wix Store via Velo.
 * Called from the CRM dashboard (base.wecare.digital/store) through
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
// ---------------------------------------------------------------------------
export const getSampleProducts = webMethod(
  Permissions.Anyone,
  async () => {
    return {
      category: 'BNB CLUB',
      products: [
        {
          name: 'Visa Assistance — Tourist Visa (Single Country)',
          productType: 'digital',
          description: `<p><strong>WECARE.DIGITAL BNB CLUB — Visa Assistance</strong></p>
<p>End-to-end visa application support for a single destination country. Our dedicated visa specialists handle everything from document preparation to appointment scheduling.</p>
<h4>What's Included</h4>
<ul>
  <li>Document checklist tailored to your destination & nationality</li>
  <li>Application form filling & review</li>
  <li>Appointment booking at VFS / Embassy</li>
  <li>Cover letter & travel itinerary preparation</li>
  <li>Pre-submission document audit</li>
  <li>Real-time status tracking via WhatsApp</li>
  <li>Post-approval travel advisory</li>
</ul>
<h4>Processing Time</h4>
<p>Standard: 7–15 business days (varies by country)<br/>Express: 3–5 business days (where available, additional charges apply)</p>
<h4>Supported Destinations</h4>
<p>USA, UK, Canada, Australia, Schengen (all 27), UAE, Singapore, Thailand, Japan, South Korea, New Zealand, and 50+ more countries.</p>`,
          priceData: {
            currency: 'INR',
            price: 2999,
          },
          sku: 'BNB-VISA-SINGLE-001',
          weight: 0,
          ribbon: 'BNB CLUB',
          brand: 'WECARE.DIGITAL',
          manageVariants: false,
          customTextFields: [
            { title: 'Destination Country', maxLength: 100, mandatory: true },
            { title: 'Passport Number', maxLength: 20, mandatory: true },
            { title: 'Travel Date (approx)', maxLength: 30, mandatory: true },
          ],
          additionalInfoSections: [
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
              title: 'Refund Policy',
              description: `<p>Service fee is non-refundable once document processing begins. If visa is rejected, a 50% credit is issued toward your next application. Embassy/VFS fees are non-refundable as per their policy.</p>`,
            },
            {
              title: 'Contact',
              description: `<p>WhatsApp: +91 93309 94400<br/>Email: visa@wecare.digital<br/>Hours: Mon–Sat, 10 AM – 7 PM IST</p>`,
            },
          ],
        },
        {
          name: 'Visa Assistance — Schengen Multi-Country',
          productType: 'digital',
          description: `<p><strong>WECARE.DIGITAL BNB CLUB — Schengen Visa</strong></p>
<p>Complete Schengen visa application service covering all 27 member states. Ideal for multi-city European trips.</p>
<ul>
  <li>Schengen-specific document preparation</li>
  <li>Multi-country itinerary planning</li>
  <li>VFS appointment booking</li>
  <li>Travel insurance arrangement (Schengen-compliant)</li>
  <li>Cover letter with detailed travel plan</li>
  <li>WhatsApp status updates</li>
</ul>`,
          priceData: {
            currency: 'INR',
            price: 4999,
          },
          sku: 'BNB-VISA-SCHENGEN-001',
          weight: 0,
          ribbon: 'BNB CLUB',
          brand: 'WECARE.DIGITAL',
          manageVariants: false,
          customTextFields: [
            { title: 'Countries to Visit', maxLength: 200, mandatory: true },
            { title: 'Passport Number', maxLength: 20, mandatory: true },
            { title: 'Travel Dates', maxLength: 50, mandatory: true },
          ],
          additionalInfoSections: [
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
          ],
        },
        {
          name: 'Visa Assistance — Business / Conference Visa',
          productType: 'digital',
          description: `<p><strong>WECARE.DIGITAL BNB CLUB — Business Visa</strong></p>
<p>Specialized visa support for business travelers, conference attendees, and corporate delegations.</p>
<ul>
  <li>Business invitation letter guidance</li>
  <li>Company registration & GST documentation</li>
  <li>Conference/event registration support</li>
  <li>Priority appointment booking</li>
  <li>Express processing (where available)</li>
</ul>`,
          priceData: {
            currency: 'INR',
            price: 3999,
          },
          sku: 'BNB-VISA-BUSINESS-001',
          weight: 0,
          ribbon: 'BNB CLUB',
          brand: 'WECARE.DIGITAL',
          manageVariants: false,
          customTextFields: [
            { title: 'Destination Country', maxLength: 100, mandatory: true },
            { title: 'Purpose of Visit', maxLength: 200, mandatory: true },
            { title: 'Company Name', maxLength: 100, mandatory: true },
          ],
        },
      ],
    };
  }
);
