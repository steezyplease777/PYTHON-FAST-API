from fastapi.responses import JSONResponse


class LabelError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def label_error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "statusCode": status_code,
            "status": "error",
            "message": message,
        },
    )
