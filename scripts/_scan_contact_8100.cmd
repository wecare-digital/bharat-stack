@echo off
aws dynamodb scan --table-name stack-wecare-digital-ContactsTable --filter-expression "contains(phone, :p)" --expression-attribute-values "{\":p\":{\"S\":\"8100640044\"}}" --projection-expression "id,phone,#n,email" --expression-attribute-names "{\"#n\":\"name\"}" --output json
