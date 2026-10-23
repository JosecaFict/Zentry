class EmployeeAdministrationError(RuntimeError):
    """Base class for employee administration domain errors."""


class ResourceNotFoundError(EmployeeAdministrationError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ResourceConflictError(EmployeeAdministrationError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class InvalidEmployeeDataError(EmployeeAdministrationError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
