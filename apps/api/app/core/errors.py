from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message_fa: str, status_code: int = 400):
        self.code = code
        self.message_fa = message_fa
        self.status_code = status_code
        super().__init__(message_fa)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message_fa": exc.message_fa},
        )
