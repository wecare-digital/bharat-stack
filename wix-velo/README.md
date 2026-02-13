# Wix Velo HTTP Functions — WECARE.DIGITAL (Integration Endpoints)
# NOTE: Existing Velo code lives in wix-store/src/ — merge before deploying

## Deployment Options

### Option 1: Wix Editor (Manual)
1. Open your Wix site editor
2. Go to **Dev Mode** > **Backend & Public** > **Backend**
3. Create or open `http-functions.js`
4. Copy the contents of `backend/http-functions.js` into it
5. Publish your site

### Option 2: Wix CLI
```bash
# Install Wix CLI if not already
npm install -g @wix/cli

# Login to your Wix account
wix login

# Open local editor connected to your site
wix dev

# Publish to production
wix publish
```

## Setup

### 1. Create API Secret
In your Wix dashboard:
- Go to **Developer Tools** > **Secrets Manager**
- Create a secret named `WECARE_API_KEY`
- Set the value to a strong random string
- Use this same value as `WIX_VELO_API_KEY` in your Amplify Lambda env vars

### 2. Configure Amplify Lambda
Set these environment variables in `amplify/functions/ecommerce/wix-store/resource.ts`:
```
WIX_MODE=velo
WIX_VELO_BASE_URL=https://www.yoursite.com
WIX_VELO_API_KEY=<same value as WECARE_API_KEY secret>
```

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/_functions/products` | GET | List products (limit, skip, search, collectionId, sort, dir) |
| `/_functions/product` | GET | Single product (id) |
| `/_functions/orders` | GET | List orders (limit, skip, paymentStatus, fulfillmentStatus, email, orderNumber, customOrderNumber, dateFrom, dateTo) |
| `/_functions/order` | GET | Single order (id) |
| `/_functions/collections` | GET | List collections (limit, skip) |
| `/_functions/inventory` | GET | Product inventory (productId) |
| `/_functions/inventoryAll` | GET | All inventory (limit, skip, inStock) |
| `/_functions/stats` | GET | Store summary stats |
