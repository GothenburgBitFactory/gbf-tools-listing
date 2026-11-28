"""Output helpers for the tools-list package: logging, fatal errors, and progress display."""

import os
import sys
from enum import IntEnum


class LogLevel(IntEnum):
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4


LOG_LEVEL = LogLevel[os.getenv("LOG_LEVEL") or "INFO"]


def log_message(message, *args, label=None):
    if args:
        message = message.format(*args)
    if label is None:
        print(message)
    else:
        print(f"\033[2K\r[{label}]", message)


def log_trace(message, *args):
    if LOG_LEVEL > LogLevel.TRACE:
        return
    log_message(message, *args, label="TRACE")


def log_debug(message, *args):
    if LOG_LEVEL > LogLevel.DEBUG:
        return
    log_message(message, *args, label="DEBUG")


def log_info(message, *args):
    if LOG_LEVEL > LogLevel.INFO:
        return
    if LOG_LEVEL == LogLevel.INFO:
        log_message(message, *args)
    else:
        log_message(message, *args, label="INFO")


def log_warn(message, *args):
    if LOG_LEVEL > LogLevel.WARN:
        return
    log_message(message, *args, label="WARN")


def log_error(message, *args):
    if LOG_LEVEL > LogLevel.ERROR:
        return
    log_message(message, *args, label="ERROR")


def die(message, *args):
    """Report a fatal error and exit."""
    log_error(message, *args)
    sys.exit(1)


def show_progress(index, total, url):
    """Overwrite the current line with a progress indicator (terminals only)."""
    if sys.stdout.isatty():
        shown = url if len(url) <= 60 else url[:57] + "..."
        print(f"\rChecking {index}/{total}: {shown}", end="", flush=True)


def clear_progress():
    """Erase the progress indicator drawn by show_progress()."""
    if sys.stdout.isatty():
        print("\033[2K\r", end="", flush=True)
