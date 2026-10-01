function handler(event) {
  return {statusCode: 302, statusDescription: 'Found', headers: {location: {value: 'https://wecare.digital/'}, 'cache-control': {value: 'no-store'}, 'x-content-type-options': {value: 'nosniff'}, 'referrer-policy': {value: 'no-referrer'}, 'content-security-policy': {value: "default-src 'none'; frame-ancestors 'none'"}}};
}
