
with open('agents/meta_agent/notifications.py', encoding='utf-8') as f:
    content = f.read()

old = '''        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())'''

new = '''        use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() == 'true'
        if use_ssl:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_EMAIL, to_email, msg.as_string())'''

if old in content:
    content = content.replace(old, new)
    with open('agents/meta_agent/notifications.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SMTP SSL support added')
else:
    print('Pattern not found')
