// Accept Claude Opus 4.6 marketplace offer
const { BedrockClient, CreateFoundationModelAgreementCommand, GetFoundationModelAvailabilityCommand } = require('@aws-sdk/client-bedrock');

async function main() {
  const client = new BedrockClient({ region: 'us-east-1' });
  
  // Step 1: Check current availability
  console.log('Checking model availability...');
  try {
    const avail = await client.send(new GetFoundationModelAvailabilityCommand({
      modelId: 'anthropic.claude-opus-4-6-v1'
    }));
    console.log('Availability:', JSON.stringify(avail.modelAvailability || avail, null, 2));
  } catch (e) {
    console.log('Availability check:', e.name, '-', e.message.substring(0, 150));
  }

  // Step 2: Try to create agreement (subscribe)
  console.log('\nAttempting to subscribe...');
  try {
    const result = await client.send(new CreateFoundationModelAgreementCommand({
      modelId: 'anthropic.claude-opus-4-6-v1',
      offerId: 'offer-ee7a27hh4hr62'
    }));
    console.log('Subscribe SUCCESS:', JSON.stringify(result, null, 2));
  } catch (e) {
    console.log('Subscribe:', e.name, '-', e.message.substring(0, 200));
  }
}

const t = setTimeout(() => { console.log('TIMEOUT'); process.exit(1); }, 30000);
main().then(() => { clearTimeout(t); process.exit(0); }).catch(e => { console.error(e); clearTimeout(t); process.exit(1); });
