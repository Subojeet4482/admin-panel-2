"""Is service ki pehchaan + doosre panels ke links (env se)."""
import os

KEY = "payment"
NAME = "Payment Bot"
ENV_KEYS = ['OWNER_EMAIL', 'OWNER_PASSWORD', 'OWNER_PIN', 'SESSION_SECRET', 'FIREBASE_CREDENTIALS_B64']
OPTIONAL = ["PANEL_MAIN_URL", "PANEL_PAYMENT_URL", "PANEL_BACKUP_URL", "UPTIMEROBOT_API_KEY", "RENDER_API_KEY", "RENDER_SERVICE_ID"]
_ALL = [("main", "Main Panel", "PANEL_MAIN_URL"), ("payment", "Payment Bot", "PANEL_PAYMENT_URL"), ("backup", "Backup Center", "PANEL_BACKUP_URL")]


def siblings():
    """Baaki do panels (jinke URL env mein diye hain)."""
    return [{"key": k, "name": n, "url": os.environ.get(e, "").strip().rstrip("/")} for k, n, e in _ALL if k != KEY and os.environ.get(e, "").strip()]
