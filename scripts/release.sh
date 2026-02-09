#!/bin/bash
# Release automation script for OpenDataGov
# Usage: ./scripts/release.sh <version> [--dry-run]
#
# Examples:
#   ./scripts/release.sh v1.0.0          # Create LTS release
#   ./scripts/release.sh v1.1.0          # Create regular release
#   ./scripts/release.sh v1.0.1          # Create patch release
#   ./scripts/release.sh v1.0.0-rc.1     # Create release candidate
#   ./scripts/release.sh v1.1.0 --dry-run  # Test without actually releasing

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Parse arguments
if [ $# -lt 1 ]; then
    log_error "Usage: $0 <version> [--dry-run]"
    echo ""
    echo "Examples:"
    echo "  $0 v1.0.0          # LTS release"
    echo "  $0 v1.1.0          # Regular release"
    echo "  $0 v1.0.1          # Patch release"
    echo "  $0 v1.0.0-rc.1     # Release candidate"
    exit 1
fi

VERSION="$1"
DRY_RUN=false

if [ "${2:-}" == "--dry-run" ]; then
    DRY_RUN=true
    log_warning "DRY RUN MODE - No changes will be made"
fi

# Validate version format
if [[ ! $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?(\+[a-z0-9.]+)?$ ]]; then
    log_error "Invalid version format: $VERSION"
    echo "Expected: vMAJOR.MINOR.PATCH[-prerelease][+buildmetadata]"
    echo "Examples: v1.0.0, v1.1.0, v1.0.1, v1.0.0-rc.1"
    exit 1
fi

VERSION_NO_V="${VERSION#v}"
MAJOR=$(echo "$VERSION_NO_V" | cut -d. -f1)
MINOR=$(echo "$VERSION_NO_V" | cut -d. -f2)
PATCH=$(echo "$VERSION_NO_V" | cut -d. -f3 | cut -d- -f1)

# Check if LTS release
IS_LTS=false
if [[ $MINOR == "0" && $PATCH == "0" && ! $VERSION =~ - ]]; then
    IS_LTS=true
    log_info "This is an LTS release (24 months support)"
else
    log_info "This is a regular release"
fi

# Check if prerelease
IS_PRERELEASE=false
if [[ $VERSION =~ - ]]; then
    IS_PRERELEASE=true
    PRERELEASE_TAG=$(echo "$VERSION" | cut -d- -f2)
    log_warning "This is a prerelease: $PRERELEASE_TAG"
fi

# Ensure we're on the correct branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$IS_PRERELEASE" = true ]; then
    EXPECTED_BRANCH="develop"
else
    EXPECTED_BRANCH="main"
fi

if [ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]; then
    log_error "You must be on $EXPECTED_BRANCH branch to create this release"
    log_info "Current branch: $CURRENT_BRANCH"
    exit 1
fi

# Ensure working directory is clean
if [ -n "$(git status --porcelain)" ]; then
    log_error "Working directory is not clean. Commit or stash your changes."
    git status --short
    exit 1
fi

# Fetch latest changes
log_info "Fetching latest changes..."
git fetch origin

# Ensure we're up to date
if [ "$CURRENT_BRANCH" != "$(git rev-parse --abbrev-ref origin/"$CURRENT_BRANCH")" ]; then
    log_warning "Your branch is not up to date with origin/$CURRENT_BRANCH"
    read -p "Do you want to pull the latest changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git pull origin "$CURRENT_BRANCH"
    else
        log_error "Aborting release"
        exit 1
    fi
fi

# Check if tag already exists
if git rev-parse "$VERSION" >/dev/null 2>&1; then
    log_error "Tag $VERSION already exists"
    exit 1
fi

# Pre-release checklist
echo ""
log_info "=== Pre-Release Checklist ==="
echo ""

echo "1. Have all tests passed?"
read -p "   Continue? (y/n) " -n 1 -r
echo
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 1

echo "2. Has the CHANGELOG been updated?"
read -p "   Continue? (y/n) " -n 1 -r
echo
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 1

echo "3. Have database migrations been tested?"
read -p "   Continue? (y/n) " -n 1 -r
echo
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 1

echo "4. Has the documentation been updated?"
read -p "   Continue? (y/n) " -n 1 -r
echo
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 1

if [ "$IS_LTS" = true ]; then
    echo "5. LTS releases require security audit. Has it been completed?"
    read -p "   Continue? (y/n) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# Run tests
echo ""
log_info "Running tests..."
if ! pytest tests/ -v; then
    log_error "Tests failed. Fix issues before releasing."
    exit 1
fi
log_success "All tests passed"

# Update version in files
echo ""
log_info "Updating version in files..."

# Update pyproject.toml files
find libs/python -name "pyproject.toml" -type f | while read -r file; do
    log_info "Updating $file"
    if [ "$DRY_RUN" = false ]; then
        sed -i.bak "s/^version = .*/version = \"$VERSION_NO_V\"/" "$file"
        rm -f "$file.bak"
    fi
done

# Update Helm Chart.yaml
if [ -f "deploy/helm/opendatagov/Chart.yaml" ]; then
    log_info "Updating deploy/helm/opendatagov/Chart.yaml"
    if [ "$DRY_RUN" = false ]; then
        yq eval ".version = \"$VERSION_NO_V\"" -i deploy/helm/opendatagov/Chart.yaml
        yq eval ".appVersion = \"$VERSION_NO_V\"" -i deploy/helm/opendatagov/Chart.yaml
    fi
fi

# Update __version__ in Python packages
find libs/python -name "__init__.py" -path "*/src/*" -type f | while read -r file; do
    if grep -q "__version__" "$file"; then
        log_info "Updating $file"
        if [ "$DRY_RUN" = false ]; then
            sed -i.bak "s/__version__ = .*/__version__ = \"$VERSION_NO_V\"/" "$file"
            rm -f "$file.bak"
        fi
    fi
done

log_success "Version files updated"

# Commit version bump
if [ "$DRY_RUN" = false ]; then
    log_info "Committing version bump..."
    git add .
    git commit -m "chore: bump version to $VERSION

This commit updates version numbers across the codebase.

$( [ "$IS_LTS" = true ] && echo "🌟 LTS Release (24 months support)" || echo "📦 Regular Release" )
$( [ "$IS_PRERELEASE" = true ] && echo "⚠️  Prerelease: $PRERELEASE_TAG" || echo "" )

Signed-off-by: Release Bot <noreply@opendatagov.io>"
    log_success "Version bump committed"
else
    log_info "DRY RUN: Would commit version bump"
fi

# Create Git tag
echo ""
log_info "Creating Git tag: $VERSION"

TAG_MESSAGE="Release $VERSION

$( [ "$IS_LTS" = true ] && echo "🌟 LTS Release
Support Window: 24 months
EOL Date: $(date -d "+2 years" +%Y-%m-%d)" || echo "📦 Regular Release" )

$( [ "$IS_PRERELEASE" = true ] && echo "⚠️  Prerelease: Not for production use" || echo "✅ Stable Release" )

Release Notes:
https://github.com/opendatagov/opendatagov/releases/tag/$VERSION

Upgrade Guide:
https://docs.opendatagov.io/upgrade/$VERSION

Signed-off-by: Release Bot <noreply@opendatagov.io>"

if [ "$DRY_RUN" = false ]; then
    git tag -a "$VERSION" -m "$TAG_MESSAGE"
    log_success "Tag created: $VERSION"
else
    log_info "DRY RUN: Would create tag $VERSION"
fi

# Push changes
echo ""
if [ "$DRY_RUN" = false ]; then
    log_info "Pushing changes to origin..."
    git push origin "$CURRENT_BRANCH"
    git push origin "$VERSION"
    log_success "Changes pushed to origin"
else
    log_info "DRY RUN: Would push changes and tag to origin"
fi

# Create release branch for LTS
if [ "$IS_LTS" = true ] && [ "$DRY_RUN" = false ]; then
    RELEASE_BRANCH="release/v${MAJOR}.${MINOR}.x"
    log_info "Creating LTS release branch: $RELEASE_BRANCH"

    git checkout -b "$RELEASE_BRANCH"
    git push origin "$RELEASE_BRANCH"
    git checkout "$CURRENT_BRANCH"

    log_success "LTS release branch created: $RELEASE_BRANCH"
fi

# Summary
echo ""
log_success "=== Release $VERSION Created Successfully! ==="
echo ""
log_info "Next Steps:"
echo "  1. GitHub Actions will automatically:"
echo "     - Run tests and security scans"
echo "     - Build Docker images"
echo "     - Build and publish Helm charts"
echo "     - Create GitHub Release with changelog"
echo "     - Send notifications (Slack, email)"
echo ""
echo "  2. Monitor the release pipeline:"
echo "     https://github.com/opendatagov/opendatagov/actions"
echo ""
echo "  3. Once pipeline completes, verify:"
echo "     - GitHub Release: https://github.com/opendatagov/opendatagov/releases/tag/$VERSION"
echo "     - Docker images: ghcr.io/opendatagov/*:$VERSION_NO_V"
echo "     - Helm chart: oci://ghcr.io/opendatagov/opendatagov:$VERSION_NO_V"
echo ""

if [ "$IS_LTS" = true ]; then
    log_info "🌟 LTS Release Information:"
    echo "  - Support Window: 24 months"
    echo "  - EOL Date: $(date -d "+2 years" +%Y-%m-%d)"
    echo "  - Release Branch: release/v${MAJOR}.${MINOR}.x"
    echo "  - Security patches will be backported"
    echo ""
fi

if [ "$IS_PRERELEASE" = true ]; then
    log_warning "⚠️  Prerelease Notice:"
    echo "  - Not recommended for production use"
    echo "  - No support provided"
    echo "  - Breaking changes may occur"
    echo ""
fi

log_success "Release process complete! 🚀"
