@echo off
aws dynamodb scan --table-name base-wecare-digital-MessagesTable --filter-expression "contains(senderPhone, :p)" --expression-attribute-values "{\":p\":{\"S\":\"8100640044\"}}" --projection-expression "id,senderPhone,messageType,paymentStatus,paymentReferenceId,#s,content" --expression-attribute-names "{\"#s\":\"status\"}" --limit 20 --output json
