"""Give councils a right of reply once their data has been checked.

Run:
  python scripts/right_of_reply.py
      lists councils that are ready (every cell human-verified or better, and not yet
      contacted) and councils whose reply date has passed; writes a draft email for
      each ready council to export/right-of-reply/<CODE>.txt (not committed)
  python scripts/right_of_reply.py --mark-sent SHR --to planning@shropshire.gov.uk
      records that you sent it: adds 'right-of-reply' to SHR/_lpa.yaml with today's
      date and a reply-by date 28 days later (change with --days)

This script doesn't send email itself: copy the draft into your own email.
The idea comes from Climate Emergency UK's council scorecards, where telling each
council directly and giving it a reply window got far more councils involved.
"""

import argparse
from datetime import date, timedelta

from common import ROOT, SPEC, load_yaml, lpa_folders, write_yaml
import review

SITE = "https://open-validation.github.io/open-validation/docs/"
REPO = "https://github.com/Open-Validation/open-validation"
OUT = ROOT / "export" / "right-of-reply"
READY = {"human-verified", "council-verified", "council-updated"}


def draft(code, lpa):
    """The text of the email to one council."""
    email = (lpa.get("contact") or {}).get("planning-email") or "<planning email: find it on the council's site>"
    vl = lpa.get("validation-list") or {}
    return f"""To: {email}
Subject: Your local validation requirements on open-validation: please check

Dear planning team,

open-validation is an independent, open data project that publishes every English
council's local validation requirements in one consistent format, based on MHCLG's
planning application data specification.

A volunteer has checked {lpa.get('name')}'s entry against your validation list:
  {vl.get('url', '')}{f" (dated {vl.get('date')})" if vl.get('date') else ''}

You can see it here:
  {SITE}#lpa={code}

We would be grateful if you could confirm it is correct, or tell us what needs changing,
by {(date.today() + timedelta(days=28)).isoformat()}. On the page, use "I work for this council",
or reply to this email. Once you confirm it, your entry will be shown as verified by the council.

The data is free for anyone to use (CC BY 4.0): {REPO}

Kind regards,
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mark-sent", metavar="CODE", help="record that the email to this council was sent")
    p.add_argument("--to", default="", help="the address you sent it to")
    p.add_argument("--days", type=int, default=28, help="days the council has to reply (default 28)")
    a = p.parse_args()

    if a.mark_sent:
        path = SPEC / a.mark_sent / "_lpa.yaml"
        lpa = load_yaml(path)
        marks = lpa.pop("field-status", {})
        lpa["right-of-reply"] = {"sent": date.today().isoformat(),
                                 "reply-by": (date.today() + timedelta(days=a.days)).isoformat()}
        if a.to:
            lpa["right-of-reply"]["to"] = a.to
        lpa["field-status"] = marks  # keep field-status last
        write_yaml(path, lpa)
        print(f"Recorded: email sent to {a.mark_sent}, reply by {lpa['right-of-reply']['reply-by']}.")
        return

    ready, overdue = [], []
    today = date.today().isoformat()
    for folder in lpa_folders():
        lpa = load_yaml(folder / "_lpa.yaml")
        rr = lpa.get("right-of-reply")
        status = lpa.get("review-status")
        if status in READY and not rr:
            ready.append((folder.name, lpa))
        elif rr and status == "human-verified" and str(rr.get("reply-by", "")) < today:
            overdue.append((folder.name, lpa, rr))

    if ready:
        OUT.mkdir(parents=True, exist_ok=True)
        print(f"{len(ready)} council(s) ready for a right-of-reply email (drafts in export/right-of-reply/):")
        for code, lpa in ready:
            (OUT / f"{code}.txt").write_text(draft(code, lpa), encoding="utf-8")
            print(f"  - {code} {lpa.get('name')}")
    else:
        print("No councils are ready yet (a council is ready when every cell is human-verified or better).")
    if overdue:
        print(f"\n{len(overdue)} council(s) haven't replied by their date:")
        for code, lpa, rr in overdue:
            print(f"  - {code} {lpa.get('name')}: sent {rr.get('sent')}, reply was due {rr.get('reply-by')}")


if __name__ == "__main__":
    main()
