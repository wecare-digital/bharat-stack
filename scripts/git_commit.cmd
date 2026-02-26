@echo off
git add -A
git status --short
git commit -m "fix: invoice image display in inbox, stuck invoice status, payment config default"
git push origin base
