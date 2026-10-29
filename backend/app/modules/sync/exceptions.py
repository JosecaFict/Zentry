class SyncError(RuntimeError):
    status_code = 400

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class SyncForbiddenError(SyncError):
    status_code = 403


class SyncNotFoundError(SyncError):
    status_code = 404


class SyncConflictError(SyncError):
    status_code = 409

