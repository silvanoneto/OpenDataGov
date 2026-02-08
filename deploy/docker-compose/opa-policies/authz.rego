package authz

import rego.v1

default allow := false

# Allow if user has admin role
allow if {
    input.roles[_] == "admin"
}

# Allow read access for any authenticated user
allow if {
    input.action == "read"
    count(input.roles) > 0
}

# Allow write access for responsible and accountable roles
allow if {
    input.action == "write"
    input.roles[_] == "responsible"
}

allow if {
    input.action == "write"
    input.roles[_] == "accountable"
}
