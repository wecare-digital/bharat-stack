@echo off
curl -s -X POST "https://api.wecare.digital/whatsapp/send" -H "Content-Type: application/json" -d "{\"contactId\":\"d800e723-6a84-419e-aa13-97b77fad9ac8\",\"phoneNumberId\":\"phone-number-id-5e020cecd221429996f6ae721cc42206\",\"content\":\"Test from Kiro - payment check\",\"isInteractivePayment\":false}" 2>&1
