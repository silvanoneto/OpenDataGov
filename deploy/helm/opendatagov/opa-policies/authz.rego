package authz

import rego.v1

# Default deny
default allow := false

# RACI role mappings (ADR-013)
required_role := "data_owner" if {
    input.action in ["create_decision", "assign_role", "exercise_veto"]
}

required_role := "data_steward" if {
    input.action in ["submit_decision", "approve_decision", "quality_check"]
}

required_role := "data_consumer" if {
    input.action in ["read_decision", "read_dataset", "query_data"]
}

required_role := "data_architect" if {
    input.action in ["define_schema", "create_contract", "modify_lineage"]
}

# Allow if user has required role
allow if {
    input.roles[_] == required_role
}

# Resource-based access control by classification
accessible_resource if {
    input.resource_classification == "public"
}

accessible_resource if {
    input.resource_classification == "internal"
    input.roles[_] in ["data_consumer", "data_steward", "data_owner", "data_architect"]
}

accessible_resource if {
    input.resource_classification == "confidential"
    input.roles[_] in ["data_steward", "data_owner"]
}

accessible_resource if {
    input.resource_classification == "secret"
    input.roles[_] == "data_owner"
}

# Domain-scoped permissions
allow if {
    input.domain_id
    user_has_domain_access
}

user_has_domain_access if {
    # Check if user has role assignment in this domain
    input.user_domains[_] == input.domain_id
}
