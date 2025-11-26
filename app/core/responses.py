def success_response(message: str, **kwargs) -> dict:
    """Return dict for consistent API responses. Validated by response_model."""
    response = {"message": message}
    if kwargs:
        response["data"] = kwargs
    return response
