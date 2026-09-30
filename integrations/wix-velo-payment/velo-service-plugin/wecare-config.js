// Paste into the Wix-generated wecare-config.js payment-provider file.
export function getConfig() {
  return {
    title: 'WECARE.DIGITAL',
    paymentMethods: [{ hostedPage: {
      title: 'Pay securely with WECARE.DIGITAL',
      billingAddressMandatoryFields: ['FIRST_NAME', 'LAST_NAME', 'EMAIL', 'PHONE', 'COUNTRY_CODE']
    } }],
    credentialsFields: [{ simpleField: { name: 'accountId', label: 'WECARE merchant account ID' } }]
  };
}
