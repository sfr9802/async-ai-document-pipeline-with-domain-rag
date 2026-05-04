# Catalog Field Reference

`source_file.status` becomes `READY` only after a catalog import has produced searchable units.
`label_status=draft` means the row is a diagnostic seed that still needs review.
`label_status=bound` means the row has source and chunk identifiers from the current live catalog.
Track B text canaries use `parserVersion=text-import-v1` and `sourceFileType=TEXT`.
