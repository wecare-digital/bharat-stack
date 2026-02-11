import boto3
polly = boto3.client("polly", region_name="us-east-1")
s3 = boto3.client("s3", region_name="us-east-1")

text = "Thank you for calling Wecare Digital. We are currently unable to take your call. Please leave a message on WhatsApp and we will get back to you shortly. Thank you."

r = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId="Kajal", Engine="neural", LanguageCode="en-IN")
audio = r["AudioStream"].read()
print(f"Generated: {len(audio)} bytes")

s3.put_object(Bucket="app.wecare.digital", Key="stream/media/ivr/ivr-greeting.mp3", Body=audio, ContentType="audio/mpeg")
print("Uploaded to stream/media/ivr/ivr-greeting.mp3")
