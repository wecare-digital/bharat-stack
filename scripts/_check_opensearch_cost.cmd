@echo off
echo === Checking OpenSearch Costs ===
aws ce get-cost-and-usage --time-period Start=2025-02-01,End=2025-02-28 --granularity DAILY --metrics BlendedCost --filter file://scripts/_opensearch_filter.json --region us-east-1 --output json --query "ResultsByTime[-7:]"
