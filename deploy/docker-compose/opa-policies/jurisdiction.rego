package authz.jurisdiction

import rego.v1

# Data residency enforcement (ADR-074)

default allow_transfer := false

# Allow transfer within same jurisdiction
allow_transfer if {
    input.source_jurisdiction == input.target_jurisdiction
}

# Allow transfer from non-restricted jurisdictions
allow_transfer if {
    not restricted_jurisdictions[input.source_jurisdiction]
}

# Global data can be transferred anywhere
allow_transfer if {
    input.source_jurisdiction == "global"
}

restricted_jurisdictions["eu"] := true
restricted_jurisdictions["br"] := true
