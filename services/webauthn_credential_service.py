"""
Persist WebAuthn credentials in Supabase (webauthn_credentials table).
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

from config import Config
from services.customer_auth_service import _sanitize_url


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class WebAuthnCredentialService:
    def __init__(self):
        if not Config.SUPABASE_URL:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        key = (Config.SUPABASE_SERVICE_ROLE_KEY or Config.SUPABASE_KEY or "").strip()
        if not key:
            raise ValueError("Supabase configuration missing (set SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY)")
        self.client: Client = create_client(url, key)
        self.table = "webauthn_credentials"

    def list_for_customer(self, customer_id: str) -> List[Dict[str, Any]]:
        if not customer_id:
            return []
        try:
            res = (
                self.client.table(self.table)
                .select("id, credential_id, sign_count, transports, friendly_name, created_at")
                .eq("customer_id", str(customer_id))
                .order("created_at", desc=False)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logging.warning("webauthn list_for_customer: %s", e)
            return []

    def get_internal_by_credential_id(self, credential_id_b64url: str) -> Optional[Dict[str, Any]]:
        """Full row for authentication verification (includes public_key, customer_id)."""
        if not credential_id_b64url:
            return None
        try:
            res = (
                self.client.table(self.table)
                .select("*")
                .eq("credential_id", credential_id_b64url)
                .limit(1)
                .execute()
            )
            if not res.data:
                return None
            return res.data[0]
        except Exception as e:
            logging.warning("webauthn get_internal_by_credential_id: %s", e)
            return None

    def save_credential(
        self,
        customer_id: str,
        credential_id_b64url: str,
        public_key: bytes,
        sign_count: int,
        transports: Optional[List[str]],
        friendly_name: Optional[str],
    ) -> bool:
        if not customer_id or not credential_id_b64url or not public_key:
            return False
        row = {
            "customer_id": str(customer_id),
            "credential_id": credential_id_b64url,
            "public_key": _b64url_encode(public_key),
            "sign_count": int(sign_count),
            "transports": transports,
            "friendly_name": (friendly_name or "").strip() or None,
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            self.client.table(self.table).insert(row).execute()
            return True
        except Exception as e:
            logging.warning("webauthn save_credential: %s", e)
            return False

    def update_sign_count(self, row_id: str, new_count: int) -> bool:
        if not row_id:
            return False
        try:
            self.client.table(self.table).update({"sign_count": int(new_count)}).eq("id", row_id).execute()
            return True
        except Exception:
            return False

    def delete_for_customer(self, customer_id: str, credential_row_id: str) -> bool:
        if not customer_id or not credential_row_id:
            return False
        try:
            self.client.table(self.table).delete().eq("id", credential_row_id).eq(
                "customer_id", str(customer_id)
            ).execute()
            return True
        except Exception:
            return False

    def delete_all_for_customer(self, customer_id: str) -> bool:
        """Delete all WebAuthn credentials for a customer (e.g. on account deletion)."""
        if not customer_id:
            return False
        try:
            self.client.table(self.table).delete().eq("customer_id", str(customer_id)).execute()
            return True
        except Exception as e:
            logging.warning("webauthn delete_all_for_customer: %s", e)
            return False
