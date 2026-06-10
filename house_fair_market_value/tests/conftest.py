import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]        # .../house_fair_market_value
ROOT = PACKAGE_DIR.parent                                # .../npw_using_loc
HOUSE_PRICE_MODEL = ROOT / "house_price_model"           # has the original `src` package

for p in (ROOT, HOUSE_PRICE_MODEL):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
