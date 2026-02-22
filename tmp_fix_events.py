"""
Fix events.js in the Wix repo:
- wixEcom_onOrderCreated does NOT exist in Wix Velo API
- Replace with wixEcom_onOrderApproved (the correct new ecom event)
- Also update the comment
"""

filepath = r'../store.wecare.digital/src/backend/events.js'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the function name
content = content.replace('wixEcom_onOrderCreated', 'wixEcom_onOrderApproved')

# Fix the comment
content = content.replace(
    'wixEcom_onOrderCreated: Generate custom order ID',
    'wixEcom_onOrderApproved: Generate custom order ID'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("OK - events.js fixed: wixEcom_onOrderCreated → wixEcom_onOrderApproved")
