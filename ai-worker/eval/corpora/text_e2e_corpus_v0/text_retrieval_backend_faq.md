# Text Retrieval Backend FAQ

`library_search` is the current Track B backend identity. It performs JPQL LIKE matching over catalog SearchUnit text fields.
`vector_text_candidate` is only a proof-of-concept wrapper and is not the operational backend for B0 or B1.
The TEXT-only filter accepts TEXT, TXT, MARKDOWN, and MD aliases but excludes PDF and SPREADSHEET rows.
Use this FAQ when comparing diagnostic library search with vector-candidate experiments.
