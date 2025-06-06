
class VaultErrors(Exception):
    def __init__(self,message):
        super().__init__(message)


class ExpirationDateError(VaultErrors):
    def __init__(self,message):
        super().__init__(message)
        self.message = message