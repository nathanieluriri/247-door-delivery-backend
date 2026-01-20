from string import Template
import os
from dotenv import load_dotenv
from . import render_localized_template

load_dotenv()

# Choose between 'sqlite' or 'mongodb'
DB_NAME = os.getenv("DB_NAME", "test").lower()

account_banned_html_templates = {
    "en": Template("""
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Account Suspended</title>
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style type="text/css">
      #outlook a { padding: 0; }
      .ReadMsgBody { width: 100%; }
      .ExternalClass { width: 100%; }
      .ExternalClass * { line-height: 100%; }
      body {
        margin: 0;
        padding: 0;
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
      }
      table, td {
        border-collapse: collapse;
        mso-table-lspace: 0pt;
        mso-table-rspace: 0pt;
      }
      img {
        border: 0;
        height: auto;
        line-height: 100%;
        outline: none;
        text-decoration: none;
        -ms-interpolation-mode: bicubic;
      }
      p { display: block; margin: 13px 0; }
    </style>

    <style type="text/css">
      @media only screen and (max-width: 480px) {
        @-ms-viewport { width: 320px; }
        @viewport { width: 320px; }
      }
    </style>
    <style type="text/css">
      @media only screen and (min-width: 480px) {
        .mj-column-per-100 {
          width: 100% !important;
          max-width: 100%;
        }
      }
      @media only screen and (max-width: 480px) {
        table.full-width-mobile { width: 100% !important; }
        td.full-width-mobile { width: auto !important; }
      }

      h1 {
        font-family: -apple-system, system-ui, BlinkMacSystemFont;
        font-size: 24px;
        font-weight: 600;
        line-height: 24px;
        text-align: left;
        color: #D32F2F; /* Changed to Red for urgency */
        padding-bottom: 18px;
      }
      p {
        font-family: -apple-system, system-ui, BlinkMacSystemFont;
        font-size: 15px;
        font-weight: 300;
        line-height: 24px;
        text-align: left;
        color: #333333;
      }
      a {
        color: #0867ec;
        font-weight: 400;
      }
      a.footer-link {
        color: #888888;
      }
      strong {
        font-weight: 500;
      }
      .alert-box {
        background-color: #fdf2f2;
        border: 1px solid #f8d7da;
        border-radius: 4px;
        padding: 15px;
        color: #721c24;
        margin-bottom: 20px;
      }
    </style>
  </head>

  <body style="background-color: #ffffff">
    <div style="display: none; font-size: 1px; color: #ffffff; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
      Important: Your $DB_NAME account has been suspended.
    </div>

    <div style="background-color: #ffffff">
      <div style="background: #ffffff; background-color: #ffffff; margin: 0px auto; max-width: 600px;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background: #ffffff; background-color: #ffffff; width: 100%">
          <tbody>
            <tr>
              <td style="direction: ltr; font-size: 0px; padding: 20px 0; text-align: center; vertical-align: top;">
                <div class="mj-column-per-100 outlook-group-fix" style="font-size: 13px; text-align: left; direction: ltr; display: inline-block; vertical-align: top; width: 100%;">
                  <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="vertical-align: top;" width="100%">
                    <tr>
                      <td align="left" style="font-size: 0px; padding: 10px 25px; word-break: break-word;">
                        <table border="0" cellpadding="0" cellspacing="0" role="presentation" style="border-collapse: collapse; border-spacing: 0px;">
                          <tbody>
                            <tr>
                              <td style="width: 54px; border-radius: 100%; ">
                                <img style=" width: 100%; height: 100%;  border-radius: 20%; transform-origin: center center; transform: scale(1.0); " alt="$DB_NAME logo"  height="auto" src="$helpful_img" style="border: 0; display: block; outline: none; text-decoration: none; height: auto; width: 100%;" width="24" />
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </td>
                    </tr>

                    <tr>
                      <td align="left" style="font-size: 0px; padding: 10px 25px 24px 25px; word-break: break-word;">
                        <div style="font-family: -apple-system, system-ui, BlinkMacSystemFont; font-size: 15px; font-weight: 300; line-height: 24px; text-align: left; color: #333333;">
                          <h1>Account Suspended</h1>
                          <p>Hi $firstName $lastName,</p>
                          
                          <p>We are writing to inform you that your $DB_NAME account has been suspended indefinitely due to a violation of our Terms of Service.</p>
                          
                          <div class="alert-box">
                            <strong>Reason for suspension:</strong><br/>
                            $reason
                          </div>

                          <p>As a result, you can no longer access your account or perform any actions on our platform.</p>
                          
                          <p>If you believe this action was taken in error, you may file an appeal by contacting our support team directly.</p>
                        </div>
                      </td>
                    </tr>

                    <tr>
                      <td align="left" style="font-size: 0px; padding: 10px 25px; word-break: break-word;">
                        <div style="font-family: -apple-system, system-ui, BlinkMacSystemFont; font-size: 15px; font-weight: 300; line-height: 24px; text-align: left; color: #333333;">
                          Regards,<br />
                          <strong>The $DB_NAME Team</strong>
                        </div>
                      </td>
                    </tr>

                    <tr>
                      <td style="font-size: 0px; padding: 10px 25px; word-break: break-word;">
                        <p style="border-top: solid 1px #e8e8e8; font-size: 1; margin: 0px auto; width: 100%;"></p>
                        </td>
                    </tr>

                    <tr>
                      <td align="left" style="font-size: 0px; padding: 10px 25px; word-break: break-word;">
                        <div style="font-family: -apple-system, system-ui, BlinkMacSystemFont; font-size: 12px; font-weight: 300; line-height: 24px; text-align: left; color: #888888;">
                          Somewhere Between Coffee & Code, Quiet Meadows, Earth 00000<br />
                          © 2025 $DB_NAME. LLC
                        </div>
                      </td>
                    </tr>

                    <tr>
                      <td align="left" style="font-size: 0px; padding: 10px 25px; word-break: break-word;">
                        <div style="font-family: -apple-system, system-ui, BlinkMacSystemFont; font-size: 12px; font-weight: 300; line-height: 24px; text-align: left; color: #888888;">
                          For appeals contact <a href="mailto:support@x.ai" class="footer-link">support@$DB_NAME.com.ng</a>
                        </div>
                      </td>
                    </tr>
                  </table>
                </div>

                </td>
            </tr>
          </tbody>
        </table>
      </div>
      </div>
  </body>
</html>
""")
}

account_banned_text_templates = {
    "en": Template("""Account suspended

Hi $firstName $lastName,

We are writing to inform you that your $DB_NAME account has been suspended indefinitely due to a violation of our Terms of Service.

Reason for suspension:
$reason

As a result, you can no longer access your account or perform any actions on our platform.

If you believe this action was taken in error, you may file an appeal by contacting our support team directly.

Regards,
The $DB_NAME Team

Somewhere Between Coffee & Code, Quiet Meadows, Earth 00000
(c) 2025 $DB_NAME, LLC
For appeals contact support@$DB_NAME.com.ng
""")
}

def generate_account_banned_email_from_template(
    firstName,
    lastName,
    reason="Violation of Terms of Service",
    locale="en",
    return_format="html",
):
    values = {
        "DB_NAME": DB_NAME,
        "helpful_img": "https://iili.io/3DKqndN.jpg",
        "firstName": firstName,
        "lastName": lastName,
        "reason": reason,
    }
    html_body = render_localized_template(
        account_banned_html_templates, locale, values, html=True
    )
    text_body = render_localized_template(
        account_banned_text_templates, locale, values, html=False
    )

    if return_format == "html":
        return html_body
    if return_format == "text":
        return text_body
    if return_format == "both":
        return {"html": html_body, "text": text_body}
    raise ValueError("return_format must be 'html', 'text', or 'both'.")
