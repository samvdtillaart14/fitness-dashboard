"""Haalt de laatste 30 dagen Garmin-data op en schrijft site/data.json."""

import json
import os
from datetime import date, datetime, timedelta
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin

TOKENS = "~/.garminconnect"  # buiten de projectmap, zodat de webserver ze nooit toont
OUT = Path(__file__).parent / "site" / "data.json"


def login():
    g = Garmin()
    try:
        g.login(TOKENS)  # eerst opgeslagen tokens proberen
        return g
    except Exception:
        pass
    print("Eerste keer inloggen bij Garmin Connect (wachtwoord wordt niet opgeslagen).")
    g = Garmin(
        input("E-mail: "),
        getpass("Wachtwoord: "),
        prompt_mfa=lambda: input("MFA-code: "),
    )
    g.login(TOKENS)
    return g


def safe(fn, *args, default=None):
    """Garmin geeft soms een fout voor een dag zonder data; sla die dag dan over."""
    try:
        return fn(*args) or default
    except Exception as e:
        print(f"  ! {fn.__name__}{args}: {e}")
        return default


def day(g, d):
    s = safe(g.get_user_summary, d, default={})
    sleep = safe(g.get_sleep_data, d, default={}).get("dailySleepDTO") or {}
    score = ((sleep.get("sleepScores") or {}).get("overall") or {}).get("value")
    hrv = safe(g.get_hrv_data, d, default={}).get("hrvSummary") or {}
    ready = safe(g.get_training_readiness, d, default=[])  # leeg op horloges zonder Training Readiness
    return {
        # intensiteitsminuten zoals Garmin ze telt: zwaar telt dubbel
        "int_min": (s.get("moderateIntensityMinutes") or 0) + 2 * (s.get("vigorousIntensityMinutes") or 0),
        "readiness": ready[0].get("score") if ready else None,
        "hrv": hrv.get("lastNightAvg"),
        "hrv_week": hrv.get("weeklyAvg"),
        "hrv_status": hrv.get("status"),
        "hrv_low": (hrv.get("baseline") or {}).get("balancedLow"),
        "hrv_high": (hrv.get("baseline") or {}).get("balancedUpper"),
        "date": d,
        "steps": s.get("totalSteps"),
        "step_goal": s.get("dailyStepGoal"),
        "rhr": s.get("restingHeartRate"),
        "hr_min": s.get("minHeartRate"),
        "hr_max": s.get("maxHeartRate"),
        "stress": s.get("averageStressLevel"),
        "rest_stress_min": round((s.get("restStressDuration") or 0) / 60),
        "bb_now": s.get("bodyBatteryMostRecentValue"),
        "bb_high": s.get("bodyBatteryHighestValue"),
        "sleep_h": round((sleep.get("sleepTimeSeconds") or 0) / 3600, 2) or None,
        "deep_h": round((sleep.get("deepSleepSeconds") or 0) / 3600, 2) or None,
        "sleep_score": score,
    }


DAYS = 30


def main():
    g = login()
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(DAYS - 1, -1, -1)]
    # Dagen ouder dan gisteren veranderen niet meer: hergebruik ze, scheelt ~80 Garmin-aanvragen per uur
    try:
        old = {d["date"]: d for d in json.loads(OUT.read_text())["days"]}
    except Exception:
        old = {}
    fresh_from = (today - timedelta(days=1)).isoformat()
    print("Data ophalen voor", dates[0], "t/m", dates[-1])
    days = [old[d] if d < fresh_from and d in old and "int_min" in old[d] else day(g, d) for d in dates]

    t = dates[-1]
    # Stappen per kwartier (voor de activiteitsbalk)
    steps15 = [
        {"t": x["startGMT"], "steps": x.get("steps", 0)}
        for x in safe(g.get_steps_data, t, default=[])
    ]
    # Stresswaarden door de dag heen; -1/-2 = geen meting
    stress = safe(g.get_stress_data, t, default={})
    stress_vals = [v for _, v in stress.get("stressValuesArray") or [] if v is not None and v >= 0]

    # Alle trainingen van het afgelopen jaar (voor lijst en totalen per maand)
    year_ago = (today - timedelta(days=365)).isoformat()
    activities = [
        {
            "name": a.get("activityName"),
            "type": (a.get("activityType") or {}).get("typeKey"),
            "start": a.get("startTimeLocal"),
            "min": round((a.get("duration") or 0) / 60),
            "km": round((a.get("distance") or 0) / 1000, 2),
            "hr": a.get("averageHR"),
        }
        for a in safe(g.get_activities_by_date, year_ago, t, default=[])
    ]
    activities.sort(key=lambda a: a["start"] or "", reverse=True)
    # VO2 max over het afgelopen jaar (Garmin meet dit alleen bij hardlopen/fietsen buiten)
    vo2 = [
        {"date": x["generic"]["calendarDate"], "value": x["generic"].get("vo2MaxPreciseValue") or x["generic"].get("vo2MaxValue")}
        for x in safe(g.get_max_metrics_range, year_ago, t, default=[])
        if x.get("generic")
    ]

    data = {
        "updated": datetime.now().isoformat(timespec="minutes"),
        "name": safe(g.get_full_name, default=""),
        "days": days,
        "steps15": steps15,
        "stress_today": stress_vals,
        "activities": activities,
        "vo2": vo2,
        # Geheim adres van de Apps Script-agenda; komt alleen versleuteld online
        "cal": os.environ.get("CAL_URL"),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))
    print("Klaar:", OUT)


if __name__ == "__main__":
    main()
