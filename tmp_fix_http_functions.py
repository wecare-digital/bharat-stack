"""
Fix http-functions.js in the Wix repo:
1. Add optional chaining for request.query in store endpoints (products, orders, collections, etc.)
2. Enhance formatOrder to look up WD-ORD from OrderIDs collection
"""
import re

filepath = r'../store.wecare.digital/src/backend/http-functions.js'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# ---- FIX 1: request.query → (request.query || {}) in store endpoints ----
# The store endpoints (get_products, get_product, get_orders, get_order, get_collections,
# get_inventory, get_inventoryAll, get_stats) use request.query.X without optional chaining.
# The SEO endpoints already use request.query?.X which is fine.
# We need to add `const q = request.query || {};` after the storeAuth check and replace
# request.query.X with q.X in each function.

# Simpler approach: just replace all `request.query.` with `(request.query || {}).` 
# in the store section (after line ~1390). But that's fragile.
# Better: replace specific patterns.

# Actually the simplest safe fix: replace `request.query.limit` etc with `request.query?.limit`
# This uses optional chaining which is supported in Wix Velo (ES2020+)

# Find all instances of request.query.SOMETHING (without ?) in the store section
# The store section starts around "function formatProduct" 
store_section_start = content.find('function formatProduct(p)')
if store_section_start == -1:
    print("ERROR: Could not find formatProduct function")
    exit(1)

before = content[:store_section_start]
after = content[store_section_start:]

# Replace request.query.X with request.query?.X (only where ? is not already there)
# Pattern: request.query. followed by a word char, but NOT request.query?.
fixed_after = re.sub(r'request\.query\.(?!\?)', 'request.query?.', after)

content = before + fixed_after

# ---- FIX 2: Enhance formatOrder to look up WD-ORD from OrderIDs ----
# Current: const customOrderNumber = o.customField?.value || '';
# Problem: customField is never set on Stores/Orders (it's read-only from data API)
# Solution: Make formatOrder async and look up from OrderIDs collection
# Actually, making formatOrder async would require changing all callers.
# Better approach: Add a post-processing step in get_orders and get_order
# that enriches orders with WD-ORD numbers from OrderIDs collection.

# Let's add a helper function and modify get_orders/get_order to use it.

# Add helper function before formatProduct
helper_code = """
// ---------- WD-ORD lookup helper ----------
async function enrichOrdersWithWdNumbers(orders) {
  if (!orders || orders.length === 0) return orders;
  try {
    const orderIds = orders.map(o => o._id).filter(Boolean);
    if (orderIds.length === 0) return orders;
    
    // Look up WD-ORD numbers from OrderIDs collection (primary source)
    const results = await wixData.query('OrderIDs')
      .hasSome('wixOrderId', orderIds)
      .limit(100)
      .find({ suppressAuth: true });
    
    const wdMap = {};
    for (const item of results.items) {
      if (item.wixOrderId && item.orderId) {
        wdMap[item.wixOrderId] = item.orderId;
      }
    }
    
    // Fallback: check OrderCustomIds for any missing
    const missing = orderIds.filter(id => !wdMap[id]);
    if (missing.length > 0) {
      const fallback = await wixData.query('OrderCustomIds')
        .hasSome('orderId', missing)
        .limit(100)
        .find({ suppressAuth: true });
      for (const item of fallback.items) {
        if (item.orderId && item.customOrderNumber) {
          wdMap[item.orderId] = item.customOrderNumber;
        }
      }
    }
    
    // Enrich orders
    return orders.map(o => {
      const wdNum = wdMap[o._id] || '';
      if (wdNum && !o.customOrderNumber) {
        o.customOrderNumber = wdNum;
      }
      if (wdNum && !o.customField?.value) {
        o.customField = { title: 'Order ID', value: wdNum };
      }
      return o;
    });
  } catch (e) {
    console.error('[http-functions] enrichOrdersWithWdNumbers error:', e?.message);
    return orders;
  }
}

"""

# Insert before formatProduct
insert_point = content.find('function formatProduct(p)')
if insert_point == -1:
    print("ERROR: Could not find formatProduct")
    exit(1)

content = content[:insert_point] + helper_code + content[insert_point:]

# Now modify get_orders to call enrichOrdersWithWdNumbers
# Current: let orders = results.items.map(formatOrder);
# New: let orders = await enrichOrdersWithWdNumbers(results.items.map(formatOrder));
content = content.replace(
    'let orders = results.items.map(formatOrder);',
    'let orders = await enrichOrdersWithWdNumbers(results.items.map(formatOrder));'
)

# Modify get_order to also enrich
# Current: return storeJson({ order: formatOrder(order) });
# We need to be careful - there are two get_order returns. Let's target the one in get_order function.
# Replace the specific pattern in get_order
old_get_order = "if (!order) return storeErr400('Order not found');\n    return storeJson({ order: formatOrder(order) });"
new_get_order = """if (!order) return storeErr400('Order not found');
    const formatted = formatOrder(order);
    const [enriched] = await enrichOrdersWithWdNumbers([formatted]);
    return storeJson({ order: enriched });"""
content = content.replace(old_get_order, new_get_order)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK - http-functions.js patched successfully")
print(f"File size: {len(content)} chars")
