from __future__ import annotations

import typing
from enum import IntFlag

__all__: typing.Sequence[str] = ("Permissions",)


@typing.final
class Permissions(IntFlag):
    NONE = 0, "No permissions"
    ME = 1 << 0, "Read info about the current user."
    VIEW_USERS = 1 << 1, "View all users."
    DELETE_USERS = 1 << 2, "Delete users."
    EDIT_USERS = 1 << 3, "Edit users."
    DISABLE_2FA = 1 << 4, "Disable 2FA for users."

    @classmethod
    def all_permissions(cls) -> Permissions:
        """Get an instance of `Permissions` with all the known permissions.

        Returns
        -------
        Permissions
            A permissions instance with all the known permissions.
        """
        all_perms = Permissions.NONE
        for perm in Permissions:
            all_perms |= perm

        return all_perms

    def __str__(self):
        return str(self.get_scopes())

    def get_scopes(self) -> typing.List[str]:
        """Get a set of permissions from the current permissions instance.

        Returns
        -------
        Set[Permissions]
            A set of permissions.
        """
        scopes: typing.List[str] = []
        for perm in Permissions:
            if self.value & perm.value:
                if perm.name is not None:
                    scopes.append(perm.name)
        return scopes

    def gs(self) -> list[str]:
        return self.get_scopes()

    def has_permission(self, permission: Permissions) -> bool:
        """Check if the current permissions instance has a permission.

        Parameters
        ----------
        permission: Permissions
            The permission to check.

        Returns
        -------
        bool
            Whether the current permissions instance has the permission.
        """
        return bool(self.value & permission.value)

    def __new__(cls, *args, **kwargs):
        obj = int.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _: int, description: str):
        self._description_ = description

    # this makes sure that the description is read-only
    @property
    def description(self) -> str:
        return self._description_
