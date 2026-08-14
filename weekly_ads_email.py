#!/usr/bin/env python3
"""
Weekly Google Ads Review - Email Sender
Generates the weekly report and sends it via SendGrid.

Requires:
  SENDGRID_API_KEY env var
  SENDGRID_FROM_EMAIL env var (verified sender in SendGrid)
"""

import os
import re
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, HtmlContent

from weekly_ads_review import generate_report


def markdown_to_html(md):
    """Basic markdown to HTML conversion for email."""
    lines = md.split("\n")
    html_lines = []
    in_table = False

    for line in lines:
        # Headers
        if line.startswith("# "):
            html_lines.append(f"<h1 style='color:#1a1a2e;'>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2 style='color:#16213e; border-bottom:1px solid #ddd; padding-bottom:5px;'>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3 style='color:#0f3460;'>{line[4:]}</h3>")
        # Table
        elif line.startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if all(set(c) <= set("- :") for c in cells):
                continue
            if not in_table:
                html_lines.append("<table style='border-collapse:collapse; width:100%; margin:10px 0;'>")
                in_table = True
                row_html = "".join(f"<th style='border:1px solid #ddd; padding:8px; background:#f2f2f2; text-align:left;'>{c}</th>" for c in cells)
                html_lines.append(f"<tr>{row_html}</tr>")
            else:
                row_html = "".join(f"<td style='border:1px solid #ddd; padding:8px;'>{c}</td>" for c in cells)
                html_lines.append(f"<tr>{row_html}</tr>")
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            if line.strip() == "---":
                html_lines.append("<hr style='border:1px solid #eee;'>")
            elif line.startswith("- "):
                html_lines.append(f"<li style='margin:3px 0;'>{line[2:]}</li>")
            elif line.strip():
                html_lines.append(f"<p style='margin:5px 0;'>{line}</p>")

    if in_table:
        html_lines.append("</table>")

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px; margin: 0 auto; padding: 20px; color: #333;">
        {"".join(html_lines)}
        <hr style='border:1px solid #eee; margin-top:30px;'>
        <div style='background:#f8f9fa; border:1px solid #e9ecef; border-radius:6px; padding:15px; margin:15px 0; font-size:13px; color:#666;'>
            <strong style='color:#444;'>How this works:</strong> This report is generated automatically every Monday morning
            by a script running on Sage's desktop computer. It pulls the last 7 days of Google Ads data
            from all accounts under the SageRock MCC via the Google Ads API, compares it to the previous
            week, and flags any issues (high spend with no conversions, low CTR, expensive CPCs, etc.).<br><br>
            <strong style='color:#444;'>Files:</strong> <code>/home/sage/scripts/sagerock-marketing-tools/weekly_ads_email.py</code><br>
            <strong style='color:#444;'>Cron:</strong> Every Monday at 8:07 AM (system crontab)<br>
            <strong style='color:#444;'>Logs:</strong> <code>/home/sage/scripts/sagerock-marketing-tools/logs/weekly_ads_email.log</code><br>
            <strong style='color:#444;'>Note:</strong> If Sage's desktop is off on Monday morning, the report won't send until the next Monday. Reports are also saved locally in <code>reports/</code>.
        </div>
        <p style='color:#999; font-size:12px;'>
            Generated automatically by Weekly Ads Review<br>
            {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
        </p>
    </div>
    """


def send_email(report_md, to_email=["sage@sagerock.com", "rocky@sagerock.com", "indy@sagerock.com"]):
    """Send the report via SendGrid."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")

    if not api_key:
        print("Error: SENDGRID_API_KEY environment variable not set.")
        return False
    if not from_email:
        print("Error: SENDGRID_FROM_EMAIL environment variable not set.")
        print("  This should be a verified sender in your SendGrid account.")
        return False

    html_content = markdown_to_html(report_md)

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=f"Weekly Google Ads Review - {datetime.now().strftime('%B %d, %Y')}",
        html_content=html_content,
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        print(f"Email sent to {to_email} (status: {response.status_code})")
        return 200 <= response.status_code < 300
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def main():
    print("Generating weekly Google Ads review...")
    report = generate_report()

    # Save report
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"reports/weekly_ads_review_{timestamp}.md"
    with open(filename, "w") as f:
        f.write(report)
    print(f"Report saved to {filename}")

    # Send email
    if not send_email(report):
        raise RuntimeError("Weekly Google Ads report email failed")


if __name__ == "__main__":
    main()
