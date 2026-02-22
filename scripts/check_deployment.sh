#!/bin/bash
# Quick deployment check for Lumo 22 on Railway
# Usage: ./scripts/check_deployment.sh
# Or: ./scripts/check_deployment.sh https://your-custom-domain.com

BASE="${1:-https://lumo22.com}"
echo "Checking $BASE"
echo ""

check() {
  local path="$1"
  local expect="$2"
  local url="$BASE$path"
  local out
  out=$(curl -sL -o /dev/null -w "%{http_code}" "$url")
  printf "  %-25s HTTP %s" "$path" "$out"
  if [ "$out" = "$expect" ]; then
    echo " ✓"
  else
    echo " (expected $expect)"
  fi
}

echo "Pages:"
check "/" "200"
check "/login" "200"
check "/signup" "200"
check "/forgot-password" "200"
check "/account" "302"
check "/captions" "200"
check "/digital-front-desk" "200"
check "/activate" "200"
check "/website-chat" "200"
check "/terms" "200"

echo ""
echo "Content check (login should say 'Digital Front Desk, Chat, and Captions'):"
if curl -sL "$BASE/login" | grep -q "Digital Front Desk, Chat, and Captions"; then
  echo "  Login page: NEW design ✓"
else
  echo "  Login page: OLD design (shows 'lead dashboard')"
fi

if curl -sL "$BASE/forgot-password" | grep -q "Forgot password"; then
  echo "  Forgot password: exists ✓"
else
  echo "  Forgot password: missing or wrong"
fi

echo ""
echo "Done."
