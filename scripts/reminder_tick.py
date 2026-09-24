import os
import urllib.request


def main():
    token = os.environ["REMINDER_CRON_TOKEN"]
    request = urllib.request.Request(
        "https://originalkopya.onrender.com/internal/reminders/tick/",
        method="POST",
        headers={"X-Reminder-Token": token},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
