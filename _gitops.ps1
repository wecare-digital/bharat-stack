cd "c:\Users\base\Desktop\stack\stack.wecare.digital"
git add -A 2>&1 | Out-File -FilePath gitops.txt -Encoding utf8
git --no-pager commit -m "feat(monitoring): expand log-retention to all deployed lambdas; fix global error-rate alarm; add DLQ-depth alarms for all 3 DLQs, bulk-queue stuck alarm, lambda throttle alarm; broaden per-lambda critical alarms" 2>&1 | Out-File -FilePath gitops.txt -Append -Encoding utf8
git --no-pager push origin stack 2>&1 | Out-File -FilePath gitops.txt -Append -Encoding utf8
"---HEAD---" | Out-File -FilePath gitops.txt -Append -Encoding utf8
git --no-pager log -1 --oneline 2>&1 | Out-File -FilePath gitops.txt -Append -Encoding utf8
git rev-parse --short origin/stack 2>&1 | Out-File -FilePath gitops.txt -Append -Encoding utf8
