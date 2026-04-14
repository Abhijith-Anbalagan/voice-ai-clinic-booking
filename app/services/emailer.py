import os
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

EMAIL_FROM   = os.getenv("EMAIL_FROM", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
APP_TZ = ZoneInfo("Asia/Kolkata")


def _build_ics(
    *,
    patient_name: str,
    patient_email: str,
    doctor_name: str,
    start_at: datetime,
    end_at: datetime,
    reason: str,
    appointment_id: int,
) -> str:
    """Generate an RFC-5545 iCalendar file (accepted by Gmail, Apple Mail, Outlook)."""
    def fmt(dt: datetime) -> str:
        return dt.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

    uid = f"medibook-appt-{appointment_id}@clinic.local"
    dtstamp = fmt(datetime.now(ZoneInfo("UTC")))

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//MediBook//Voice Clinic//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART:{fmt(start_at)}\r\n"
        f"DTEND:{fmt(end_at)}\r\n"
        f"SUMMARY:Appointment with {doctor_name}\r\n"
        f"DESCRIPTION:Patient: {patient_name}\\nReason: {reason}\\nDoctor: {doctor_name}\r\n"
        f"ORGANIZER;CN=MediBook Clinic:mailto:{EMAIL_FROM}\r\n"
        f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;"
        f"CN={patient_name}:mailto:{patient_email}\r\n"
        "STATUS:CONFIRMED\r\n"
        "SEQUENCE:0\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT60M\r\n"
        "ACTION:DISPLAY\r\n"
        f"DESCRIPTION:Reminder: Appointment with {doctor_name} in 1 hour\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def _build_html(
    *,
    patient_name: str,
    doctor_name: str,
    start_at: datetime,
    end_at: datetime,
    reason: str,
    appointment_id: int,
) -> str:
    nice_date = start_at.astimezone(APP_TZ).strftime("%A, %d %B %Y")
    nice_time = start_at.astimezone(APP_TZ).strftime("%I:%M %p")
    nice_end  = end_at.astimezone(APP_TZ).strftime("%I:%M %p")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Appointment Confirmed</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Playfair+Display:wght@700&display=swap');
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'DM Sans',Arial,sans-serif;background:#f0ece6;padding:32px 16px}}
    .wrap{{max-width:560px;margin:0 auto}}
    .header{{background:linear-gradient(135deg,#1e2530 0%,#111820 100%);border-radius:16px 16px 0 0;padding:36px 32px;text-align:center}}
    .logo{{display:inline-flex;align-items:center;gap:10px;margin-bottom:24px}}
    .logo-mark{{color:#2a9d8f;font-size:22px}}
    .logo-text{{font-family:'Playfair Display',Georgia,serif;font-size:22px;color:#fff;letter-spacing:.02em}}
    .check-circle{{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#2a9d8f,#1f7a6e);margin:0 auto 16px;display:flex;align-items:center;justify-content:center;font-size:28px;color:#fff}}
    .header-title{{font-family:'Playfair Display',Georgia,serif;font-size:26px;color:#fff;margin-bottom:8px}}
    .header-sub{{font-size:15px;color:rgba(255,255,255,.6)}}
    .body{{background:#fff;padding:32px}}
    .greeting{{font-size:17px;color:#1e2530;margin-bottom:24px;line-height:1.6}}
    .detail-card{{background:#f7f4ef;border-radius:12px;padding:24px;margin-bottom:24px;border:1px solid #ede9e2}}
    .detail-row{{display:flex;align-items:flex-start;gap:14px;padding:10px 0;border-bottom:1px solid #ede9e2}}
    .detail-row:last-child{{border-bottom:none}}
    .detail-icon{{font-size:20px;flex-shrink:0;width:28px;text-align:center}}
    .detail-label{{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:#6b7280;margin-bottom:3px}}
    .detail-value{{font-size:15px;font-weight:500;color:#1e2530}}
    .appt-id{{font-size:12px;color:#9ca3af;margin-top:2px}}
    .reminder-box{{background:#e0f5f3;border:1px solid rgba(42,157,143,.3);border-radius:10px;padding:16px 20px;margin-bottom:24px;display:flex;gap:12px;align-items:flex-start}}
    .reminder-icon{{font-size:20px;flex-shrink:0}}
    .reminder-text{{font-size:14px;color:#1f7a6e;line-height:1.6}}
    .reminder-title{{font-weight:700;margin-bottom:4px}}
    .footer{{background:#f7f4ef;border-radius:0 0 16px 16px;padding:24px 32px;text-align:center}}
    .footer-text{{font-size:13px;color:#9ca3af;line-height:1.7}}
    .footer-brand{{font-size:14px;font-weight:600;color:#4a5568;margin-bottom:6px}}
  </style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div class="header">
    <div class="logo">
      <span class="logo-mark">✦</span>
      <span class="logo-text">MediBook</span>
    </div>
    <div class="check-circle">✓</div>
    <h1 class="header-title">Appointment Confirmed</h1>
    <p class="header-sub">Your booking is all set — see you soon!</p>
  </div>

  <!-- Body -->
  <div class="body">
    <p class="greeting">Hi <strong>{patient_name}</strong>, your appointment has been successfully booked. Here are the details:</p>

    <div class="detail-card">
      <div class="detail-row">
        <div class="detail-icon">👨‍⚕️</div>
        <div>
          <div class="detail-label">Doctor</div>
          <div class="detail-value">{doctor_name}</div>
        </div>
      </div>
      <div class="detail-row">
        <div class="detail-icon">📅</div>
        <div>
          <div class="detail-label">Date</div>
          <div class="detail-value">{nice_date}</div>
        </div>
      </div>
      <div class="detail-row">
        <div class="detail-icon">🕐</div>
        <div>
          <div class="detail-label">Time</div>
          <div class="detail-value">{nice_time} – {nice_end} IST</div>
        </div>
      </div>
      <div class="detail-row">
        <div class="detail-icon">📋</div>
        <div>
          <div class="detail-label">Reason</div>
          <div class="detail-value">{reason}</div>
          <div class="appt-id">Appointment ID: #{appointment_id:04d}</div>
        </div>
      </div>
    </div>

    <div class="reminder-box">
      <div class="reminder-icon">📎</div>
      <div class="reminder-text">
        <div class="reminder-title">Calendar Invite Attached</div>
        A <strong>.ics</strong> file is attached to this email. Open it to add this appointment directly to Google Calendar, Apple Calendar, or Outlook.
      </div>
    </div>

    <div class="reminder-box" style="background:#fef9c3;border-color:rgba(202,138,4,.3)">
      <div class="reminder-icon">⏰</div>
      <div class="reminder-text" style="color:#713f12">
        <div class="reminder-title">Reminder</div>
        Please arrive 10 minutes early and bring any relevant medical records or prescriptions.
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <div class="footer-brand">MediBook Voice Clinic</div>
    <div class="footer-text">
      Chennai, Tamil Nadu · Mon–Sat 9am–6pm<br/>
      This is an automated confirmation email. Please do not reply.
    </div>
  </div>

</div>
</body>
</html>"""


def send_invite_email(
    *,
    patient_email: str,
    patient_name: str,
    doctor_name: str,
    start_at: datetime,
    end_at: datetime,
    reason: str,
    appointment_id: int,
) -> tuple[bool, str]:

    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("Email not configured — skipping send.")
        return False, "Email not configured (set EMAIL_FROM and EMAIL_PASSWORD in .env)"

    # Ensure datetimes are tz-aware for formatting / .ics generation
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=APP_TZ)
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=APP_TZ)

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"✦ Appointment Confirmed — {doctor_name} | MediBook"
        msg["From"]    = f"MediBook Clinic <{EMAIL_FROM}>"
        msg["To"]      = patient_email

        # Plain-text fallback
        nice = start_at.astimezone(APP_TZ).strftime("%A, %d %B %Y at %I:%M %p")
        plain = MIMEText(
            f"Hi {patient_name},\n\n"
            f"Your appointment is confirmed.\n\n"
            f"Doctor : {doctor_name}\n"
            f"Time   : {nice} IST\n"
            f"Reason : {reason}\n\n"
            f"A calendar invite (.ics) is attached — open it to add to your calendar.\n\n"
            f"Thanks,\nMediBook Clinic",
            "plain",
        )

        # HTML body
        html_body = MIMEText(
            _build_html(
                patient_name=patient_name,
                doctor_name=doctor_name,
                start_at=start_at,
                end_at=end_at,
                reason=reason,
                appointment_id=appointment_id,
            ),
            "html",
        )

        alt = MIMEMultipart("alternative")
        alt.attach(plain)
        alt.attach(html_body)
        msg.attach(alt)

        # Attach .ics calendar invite — now passes patient_email correctly
        ics_data = _build_ics(
            patient_name=patient_name,
            patient_email=patient_email,
            doctor_name=doctor_name,
            start_at=start_at,
            end_at=end_at,
            reason=reason,
            appointment_id=appointment_id,
        )
        ics_part = MIMEBase("text", "calendar", method="REQUEST", name="invite.ics")
        ics_part.set_payload(ics_data.encode("utf-8"))
        encoders.encode_base64(ics_part)
        ics_part.add_header("Content-Disposition", "attachment", filename="invite.ics")
        ics_part.add_header("Content-Type", 'text/calendar; method="REQUEST"; charset="UTF-8"')
        msg.attach(ics_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
            smtp.send_message(msg)

        return True, "Calendar invite sent to " + patient_email

    except Exception as e:
        print(f"Email error: {e}")
        return False, str(e)