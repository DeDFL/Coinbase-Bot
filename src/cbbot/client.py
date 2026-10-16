import os
import time

import pandas as pd
from coinbase.rest import RESTClient

GRANULARITY_SECONDS = {
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "THIRTY_MINUTE": 1800,
    "ONE_HOUR": 3600,
    "TWO_HOUR": 7200,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
}
MAX_CANDLES_PER_REQUEST = 350


def _authed_client() -> RESTClient | None:
    key_file = os.getenv("COINBASE_KEY_FILE", "").strip()
    if key_file:
        return RESTClient(key_file=os.path.expanduser(key_file))
    key, secret = os.getenv("COINBASE_API_KEY", "").strip(), os.getenv("COINBASE_API_SECRET", "").strip()
    if key and secret:
        return RESTClient(api_key=key, api_secret=secret.replace("\\n", "\n"))
    return None


class Coinbase:
    def __init__(self):
        self.public = RESTClient()
        self.authed = _authed_client()

    @property
    def has_key(self) -> bool:
        return self.authed is not None

    def require_key(self) -> RESTClient:
        if not self.authed:
            raise RuntimeError("No Coinbase API key configured. Add COINBASE_KEY_FILE or COINBASE_API_KEY/SECRET to .env")
        return self.authed

    def product(self, product_id: str) -> dict:
        return self.public.get_public_product(product_id).to_dict()

    def price(self, product_id: str) -> float:
        return float(self.product(product_id)["price"])

    def candles(self, product_id: str, granularity: str = "ONE_HOUR", limit: int = 300) -> pd.DataFrame:
        """Closed candles only, oldest first."""
        step = GRANULARITY_SECONDS[granularity]
        end = int(time.time()) // step * step  # start of the in-progress candle
        rows: list[dict] = []
        remaining = limit
        while remaining > 0:
            n = min(remaining, MAX_CANDLES_PER_REQUEST)
            start = end - n * step
            resp = self.public.get_public_candles(
                product_id, start=str(start), end=str(end - 1), granularity=granularity
            ).to_dict()
            batch = resp.get("candles", [])
            if not batch:
                break
            rows.extend(batch)
            remaining -= n
            end = start
        if not rows:
            return pd.DataFrame(columns=["start", "open", "high", "low", "close", "volume"])
        df = pd.DataFrame(rows).astype(float).drop_duplicates("start").sort_values("start")
        df["time"] = pd.to_datetime(df["start"], unit="s", utc=True)
        return df.reset_index(drop=True)

    def accounts(self) -> list[dict]:
        client = self.require_key()
        out, cursor = [], None
        while True:
            resp = client.get_accounts(limit=250, cursor=cursor).to_dict()
            out.extend(resp.get("accounts", []))
            if not resp.get("has_next"):
                return out
            cursor = resp.get("cursor")
