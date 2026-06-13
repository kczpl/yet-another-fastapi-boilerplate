# Error registry: short snake_case key → "api.<feature>.<key>" i18n key.
#
# Every key passed to raise_not_found / raise_bad_request / etc. must be a short
# literal registered here (never an f-string). Add a "### Feature ###" section per
# domain. tests/core/test_error_registry.py keeps raised keys and this dict in sync.
ERRORS = {
    ### General ###
    "server_error": "api.general.internal_server_error",
    "invalid_request_data": "api.general.invalid_request_data",
    "required_parameter_missing": "api.general.required_parameter_missing",
    "not_found": "api.general.not_found",
    "bad_request": "api.general.bad_request",
    "validation_error": "api.general.validation_error",
    "conflict": "api.general.conflict",
    "file_too_large": "api.general.file_too_large",
    ### Items (example feature) ###
    "item_not_found": "api.items.item_not_found",
    "item_already_summarized": "api.items.item_already_summarized",
}
