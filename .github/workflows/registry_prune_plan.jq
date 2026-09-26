def unpublished_versions($published_versions):
    [ .[] | . as $version | select(($published_versions | index($version)) == null) ];

.published as $published
| .current
| to_entries
| sort_by(.key)
| map(
    .key as $module
    | (.value // []) as $versions
    | ($versions | unpublished_versions(($published[$module] // []))) as $unpublished
    | if ($unpublished | length) > 1 then
        [ $unpublished[0:-1][] as $version | {module: $module, version: $version, kept: $unpublished[-1]} ]
      else
        []
      end
)
| add // []
