package authz.raci

import rego.v1

# RACI role to permissions mapping (ADR-013)

responsible_permissions := {"read", "write", "submit", "execute"}
accountable_permissions := {"read", "write", "approve", "reject", "veto", "escalate"}
consulted_permissions := {"read", "comment"}
informed_permissions := {"read"}

role_permissions["responsible"] := responsible_permissions
role_permissions["accountable"] := accountable_permissions
role_permissions["consulted"] := consulted_permissions
role_permissions["informed"] := informed_permissions
