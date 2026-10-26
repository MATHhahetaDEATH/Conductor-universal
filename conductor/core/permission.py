from enum import IntEnum

class PermissionLevel(IntEnum):
    """
    Permission levels mimicking the MCDR permission design.
    """
    GUEST = 0    # Lowest level (e.g. unauthenticated)
    USER = 1     # Normal API users
    HELPER = 2   # Elevated API users
    ADMIN = 3    # Administrative access
    OWNER = 4    # Highest access (Physical terminal / OpenClaw CLI)

class CommandSource:
    """
    Represents the issuer of a command.
    """
    def __init__(self, name: str, permission_level: PermissionLevel):
        self.name = name
        self.permission_level = permission_level

    def reply(self, message: str, plugin_id: str = "core") -> None:
        """Send a plain text reply back to the source."""
        raise NotImplementedError
