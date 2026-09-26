#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/../.."

run_case() {
    local name="$1"
    local input="$2"
    local expected="$3"
    local actual

    actual="$(jq -c -f .github/workflows/registry_prune_plan.jq <<< "${input}")"
    if ! diff -u <(printf '%s\n' "${expected}") <(printf '%s\n' "${actual}"); then
        echo "FAILED: ${name}" >&2
        return 1
    fi
    echo "ok: ${name}"
}

run_case \
    "never published keeps last unpublished version" \
    '{"published":{},"current":{"alpha":["1.0.envoy","2.0.envoy"],"beta":["3.0.envoy"]}}' \
    '[{"module":"alpha","version":"1.0.envoy","kept":"2.0.envoy"}]'

run_case \
    "published baseline handles zero one and many new versions" \
    '{"published":{"many":["1.0.envoy"],"one":["1.0.envoy"],"stable":["1.0.envoy"]},"current":{"many":["1.0.envoy","2.0.envoy","3.0.envoy"],"one":["1.0.envoy","2.0.envoy"],"stable":["1.0.envoy"]}}' \
    '[{"module":"many","version":"2.0.envoy","kept":"3.0.envoy"}]'

run_case \
    "mixed metadata and directory-only cases keep only the last unpublished entry" \
    '{"published":{"currentdir":["1.0.envoy"],"dironlymulti":["1.0.envoy"],"dirsync":["1.0.envoy","2.0.envoy"],"metadataonly":["1.0.envoy"]},"current":{"currentdir":["1.0.envoy","2.0.envoy","3.0.envoy"],"dironlymulti":["1.0.envoy","2.0.envoy","3.0.envoy"],"dirsync":["1.0.envoy","2.0.envoy","3.0.envoy"],"metadataonly":["1.0.envoy","2.0.envoy","3.0.envoy"]}}' \
    '[{"module":"currentdir","version":"2.0.envoy","kept":"3.0.envoy"},{"module":"dironlymulti","version":"2.0.envoy","kept":"3.0.envoy"},{"module":"metadataonly","version":"2.0.envoy","kept":"3.0.envoy"}]'

run_case \
    "brand new module removes all but latest unpublished version" \
    '{"published":{"published":["1.0.envoy"]},"current":{"fresh":["0.1.envoy","0.2.envoy","0.3.envoy"],"published":["1.0.envoy"]}}' \
    '[{"module":"fresh","version":"0.1.envoy","kept":"0.3.envoy"},{"module":"fresh","version":"0.2.envoy","kept":"0.3.envoy"}]'

run_case \
    "published version missing from current tree is ignored" \
    '{"published":{"gone":["1.0.envoy","2.0.envoy"]},"current":{"gone":["1.0.envoy"]}}' \
    '[]'
