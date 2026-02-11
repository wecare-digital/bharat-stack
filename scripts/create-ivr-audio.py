"""Generate IVR greeting audio using Amazon Polly and upload to S3."""
import boto3

polly = boto3.client("polly", region_name="us-east-1")
s3 = boto3.client("s3", region_name="us-east-1")

BUCKET = "app.wecare.digital"
KEY = "stream/media/ivr/ivr-greeting.mp3"

TEXT = """<speak>
<prosody rate="95%">
Thank you for calling Wecare Digital. 
We are currently unable to take your call. 
Please leave a message on WhatsApp and we will get back to you shortly. 
Thank you.
</prosody>
</speak>"""

print("Generating IVR audio with Amazon Polly (Kajal, Neural, Hindi-English)...")
response = polly.synthesize_speech(
    Text=TEXT,
    TextType="ssml",
    OutputFormat="mp3",
    VoiceId="Kajal",
    Engine="neural",
    LanguageCode="en-IN",
)

audio_stream = response["AudioStream"].read()
print(f"Audio generated: {len(audio_stream)} bytes")

print(f"Uploading to s3://{BUCKET}/{KEY}...")
s3.put_object(
    Bucket=BUCKET,
    Key=KEY,
    Body=audio_stream,
    ContentType="audio/mpeg",
    CacheControl="public, max-age=86400",
)
print(f"Uploaded: https://{BUCKET}/{KEY}")

# Verify it's accessible
head = s3.head_object(Bucket=BUCKET, Key=KEY)
print(f"Verified: {head['ContentLength']} bytes, ContentType={head['ContentType']}")
print(f"\nIVR URL: https://app.wecare.digital/stream/media/ivr/ivr-greeting.mp3")
