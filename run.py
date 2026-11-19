import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
    from django.core.management import execute_from_command_line

    if len(sys.argv) == 1:
        sys.argv.extend(["runserver", "127.0.0.1:8000"])
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
