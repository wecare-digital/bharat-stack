@echo off
aws dynamodb scan --table-name base-wecare-digital-ContactsTable --filter-expression "contains(phone, :p)" --expression-attribute-values "{\":p\":{\"S\":\"8330919448\"}}" --projection-expression "id,phone,#n" --expression-attribute-names "{\"#n\":\"name\"}" --output json
