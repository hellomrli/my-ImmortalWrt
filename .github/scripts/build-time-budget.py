#!/usr/bin/env python3
"""Reserve diagnostic time after accounting for all build prerequisites."""

import os
import sys
import time


def compile_minutes(started_at, now, job_minutes, reserve_minutes=30, maximum=320):
    if started_at > now or started_at <= 0 or min(job_minutes, reserve_minutes, maximum) <= 0:
        raise ValueError("invalid build clock or timeout settings")
    remaining = (started_at + job_minutes * 60 - now) // 60 - reserve_minutes
    if remaining < 1:
        raise ValueError("no compile time remains after reserving diagnostics; refusing to start make")
    return min(maximum, remaining)


def main():
    try:
        started_at = int(os.environ["BUILD_STARTED_AT"])
        job_minutes = int(os.environ["BUILD_JOB_TIMEOUT_MINUTES"])
        now = int(time.time())
        minutes = compile_minutes(started_at, now, job_minutes)
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"minutes={minutes}\n")
    except (KeyError, ValueError, OSError) as exc:
        print(f"::error::Cannot allocate compile budget: {exc}", file=sys.stderr)
        return 1
    print(f"Prerequisites used {(now - started_at) / 60:.1f} min; compile limit {minutes} min; "
          "at least 30 min reserved for diagnostics and finalization.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
