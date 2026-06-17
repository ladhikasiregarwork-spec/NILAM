from typing import Any, Optional

from pydantic import BaseModel


class FraudRequest(BaseModel):
    # Inputs accepted for contract completeness; the stub ignores them.
    slip: Optional[Any] = None
    mutasi: Optional[Any] = None
    identity: Optional[Any] = None
