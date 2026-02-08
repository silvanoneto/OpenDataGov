package authz.data_access

import rego.v1

# Row/column level access control (ADR-072)

default allow_column := true

# Deny access to PII columns unless user has appropriate role
allow_column := false if {
    input.column.is_pii == true
    not has_pii_access
}

has_pii_access if {
    input.roles[_] == "data_steward"
}

has_pii_access if {
    input.roles[_] == "admin"
}

has_pii_access if {
    input.data_classification == "public"
}
