import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
APP_TZ = ZoneInfo("Asia/Kolkata")


def _build_html(patient_name, doctor_name, nice_time, reason, appointment_id):
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Appointment Confirmed</title></head>
<body style="margin:0;padding:0;background:#f2f0ec;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f0ec;padding:40px 20px;">
    <tr><td align="center">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="max-width:580px;background:#ffffff;border-radius:24px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.09);">
        <tr>
          <td style="background:#1a1612;padding:32px 40px;">
            <table cellpadding="0" cellspacing="0"><tr>
              <td style="color:#2a5cff;font-size:20px;padding-right:10px;">✦</td>
              <td style="color:#fff;font-size:20px;font-weight:600;letter-spacing:-0.01em;">MediBook</td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="background:#0fa86e;padding:28px 40px;">
            <table cellpadding="0" cellspacing="0" width="100%"><tr>
              <td>
                <p style="margin:0 0 4px;color:rgba(255,255,255,0.75);font-size:12px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Booking confirmed</p>
                <p style="margin:0;color:#fff;font-size:26px;font-weight:600;letter-spacing:-0.02em;">Your appointment<br>is confirmed ✓</p>
              </td>
              <td align="right" valign="middle">
                <div style="width:56px;height:56px;background:rgba(255,255,255,0.2);border-radius:50%;text-align:center;line-height:56px;font-size:24px;display:inline-block;">🗓</div>
              </td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px 0;">
            <p style="margin:0 0 24px;font-size:16px;color:#1a1612;line-height:1.6;">
              Hi <strong>{patient_name}</strong>, your appointment has been booked. Here are your details:
            </p>
            <table cellpadding="0" cellspacing="0" width="100%"
                   style="background:#f7f5f2;border-radius:16px;overflow:hidden;margin-bottom:24px;">
              <tr><td style="padding:24px 28px;">
                <table cellpadding="0" cellspacing="0" width="100%">
                  <tr>
                    <td style="padding-bottom:16px;width:50%;vertical-align:top;">
                      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#9b9690;">Doctor</p>
                      <p style="margin:0;font-size:15px;font-weight:600;color:#1a1612;">{doctor_name}</p>
                    </td>
                    <td style="padding-bottom:16px;vertical-align:top;">
                      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#9b9690;">Reason</p>
                      <p style="margin:0;font-size:15px;font-weight:600;color:#1a1612;">{reason.capitalize()}</p>
                    </td>
                  </tr>
                  <tr><td colspan="2" style="border-top:1px solid #e8e4de;padding-bottom:16px;"></td></tr>
                  <tr>
                    <td colspan="2">
                      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#9b9690;">Date &amp; Time</p>
                      <p style="margin:0;font-size:20px;font-weight:700;color:#1a1612;letter-spacing:-0.01em;">{nice_time}</p>
                    </td>
                  </tr>
                </table>
              </td></tr>
            </table>
            <p style="margin:0 0 28px;font-size:13px;color:#9b9690;">
              Reference: <span style="font-family:monospace;color:#1a1612;font-weight:600;">APT-{appointment_id:05d}</span>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 40px 36px;">
            <table cellpadding="0" cellspacing="0"
                   style="background:#eef1ff;border-radius:14px;" width="100%">
              <tr><td style="padding:20px 24px;">
                <p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#2a5cff;">📋 What to bring</p>
                <p style="margin:0;font-size:13px;color:#4a5280;line-height:1.6;">
                  Please bring a valid photo ID and any previous medical records relevant to your visit. Arrive 5 minutes early.
                </p>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="background:#f7f5f2;padding:24px 40px;border-top:1px solid #e8e4de;">
            <p style="margin:0;font-size:12px;color:#9b9690;line-height:1.6;">
              This is an automated confirmation from MediBook Voice AI Clinic.<br>
              If you need to reschedule, please contact us directly.
            </p>
          </td>
        </tr>
      </table>
      <p style="margin-top:20px;font-size:11px;color:#b8b4af;">MediBook · Voice-powered clinic scheduling</p>
    </td></tr>
  </table>
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
):
    try:
        nice_time = start_at.astimezone(APP_TZ).strftime("%A, %d %B at %I:%M %p")

        msg = EmailMessage()
        msg["Subject"] = f"Appointment Confirmed with {doctor_name} — {nice_time}"
        msg["From"] = EMAIL_FROM
        msg["To"] = patient_email

        # Plain text fallback
        msg.set_content(f"""
Hi {patient_name},

Your appointment is confirmed.

Doctor : {doctor_name}
Time   : {nice_time}
Reason : {reason}
Ref    : APT-{appointment_id:05d}

Please bring a valid photo ID and any previous medical records.
Arrive 5 minutes early.

Thanks,
MediBook · Voice AI Clinic
        """.strip())

        # Rich HTML version
        html_body = _build_html(
            patient_name=patient_name,
            doctor_name=doctor_name,
            nice_time=nice_time,
            reason=reason,
            appointment_id=appointment_id,
        )
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
            smtp.send_message(msg)

        return True, "Email sent via Gmail"

    except Exception as e:
        print("Email error:", e)
        return False, str(e)