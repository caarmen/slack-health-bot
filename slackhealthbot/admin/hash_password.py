#!/usr/bin/env python3
"""
Command-line utility to generate a password hash to use with the sqladmin interface.
"""
import sys
from getpass import getpass

from passlib.hash import pbkdf2_sha256


def main():
    # Ask for password without showing it
    password = getpass("Enter password: ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match!", file=sys.stderr)
        return 1

    # Hash it
    hashed = pbkdf2_sha256.hash(password)
    print("\nSet the ADMIN_PASSWORD_HASH in your .env file to:")
    print(hashed)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
