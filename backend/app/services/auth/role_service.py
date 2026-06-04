import logging
import json
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class RoleService:
    """
    Manages Role-Based Access Control (RBAC) policies and permissions.
    Decouples role logic from the authentication service.
    """

    POLICY_FILE = os.path.join(os.path.dirname(__file__), "../../policies/permission_rules.json")

    def __init__(self):
        self._load_policies()

    def _load_policies(self):
        try:
            if os.path.exists(self.POLICY_FILE):
                with open(self.POLICY_FILE, 'r') as f:
                    self.policies = json.load(f)
            else:
                logger.warning(f"RoleService: policy file {self.POLICY_FILE} not found. Using defaults.")
                self.policies = {"roles": {}}
        except Exception as exc:
            logger.error(f"RoleService: failed to load policies — {exc}")
            self.policies = {"roles": {}}

    def get_role_permissions(self, role_name: str) -> Dict[str, Any]:
        """
        Return the permission set for a specific role.
        """
        return self.policies.get("roles", {}).get(role_name.lower(), {
            "can_export": False,
            "can_see_all_tables": False,
            "max_query_complexity": 10
        })

    def can_user_export(self, role_name: str) -> bool:
        return self.get_role_permissions(role_name).get("can_export", False)

    def get_max_complexity(self, role_name: str) -> int:
        return self.get_role_permissions(role_name).get("max_query_complexity", 20)

    def is_protected_table_blocked(self, role_name: str) -> bool:
        return self.get_role_permissions(role_name).get("protected_tables_blocked", True)

    def get_protected_tables(self) -> List[str]:
        return self.policies.get("protected_tables", [])
