# Launching CSF-CUET on Render (free)

This guide gets the forum live without losing data. It takes about 30 minutes, and every service it uses has a free plan with no credit card needed.

## Why three services and not just Render

On Render's free plan the server's disk is **temporary**. It is wiped on every deploy, every restart, **and every time the site sleeps** (after 15 idle minutes). If you use SQLite and the local `media/` folder, every member, post and photo disappears again and again.

| What | Where it lives | Why |
|---|---|---|
| Code and web server | Render (free web service) | Already set up |
| Database (members, posts, events) | **Neon** Postgres (free) | Render's free Postgres is **deleted 30 days** after you create it. Neon's free plan doesn't expire. |
| Photos (profile pictures, post images, gallery) | **Cloudinary** (free) | Photos must live outside Render's disk |
| Email (approval notices, password reset) | **Gmail** SMTP with an app password | Without it, "Forgot password" emails never arrive |

The site switches over automatically: it uses Postgres when `DATABASE_URL` is set and Cloudinary when `CLOUDINARY_URL` is set. You don't need to change any code.

---

## Step 1. Create the database (Neon)

1. Go to <https://neon.com> and sign up (GitHub sign-in works).
2. Create a project named `csf-cuet` in the region closest to Bangladesh (Singapore, `aws-ap-southeast-1`).
3. On the project dashboard, click **Connect** and copy the connection string. It looks like this:
   ```
   postgresql://neondb_owner:XXXX@ep-something-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
   This is your `DATABASE_URL`. Keep it secret.

## Step 2. Create photo storage (Cloudinary)

1. Go to <https://cloudinary.com> and sign up for the free plan.
2. On the dashboard (**Settings → API Keys**), copy the **API environment variable**. It looks like this:
   ```
   cloudinary://123456789012345:abcDEF...@your-cloud-name
   ```
   This is your `CLOUDINARY_URL`. Copy only the part that starts with `cloudinary://`.

## Step 3. Create a Gmail app password

1. Use the Gmail account the forum will send email from. An official one, such as `csf.cuet@gmail.com`, is better than your personal one.
2. Turn on **2-Step Verification**: Google Account → Security.
3. Open <https://myaccount.google.com/apppasswords>, create an app password named `CSF forum`, and copy the 16 letters.

## Step 4. Add the settings on Render

In the Render dashboard, open your web service, then **Environment → Add Environment Variable**, and add the following:

| Key | Value |
|---|---|
| `DJANGO_SECRET_KEY` | (already set) |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | the Neon string from step 1 |
| `CLOUDINARY_URL` | the Cloudinary string from step 2 |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | the Gmail address |
| `EMAIL_HOST_PASSWORD` | the 16-letter app password, without spaces |
| `DEFAULT_FROM_EMAIL` | `CSF-CUET <the Gmail address>` |
| `DJANGO_ADMIN_EMAIL` | the email you'll log in with as the main admin |
| `DJANGO_ADMIN_PASSWORD` | a strong password, at least 10 characters |
| `DJANGO_ADMIN_NAME` | your name (optional) |

Do **not** click deploy yet if you have existing members to bring over. Do step 5 first. If you're starting with an empty forum, skip to step 6.

The `DJANGO_ADMIN_*` settings make every deploy create that admin account if it's missing, or repair it if it was demoted or deactivated. The password is only used when the account is first created, so changing it later on the site is safe.

## Step 5. Move your existing data (once, from your PC)

Run this in the project folder on your PC, with the virtual environment activated, **before** the first deploy that uses Neon.

**Command Prompt (cmd):**
```bat
git pull
pip install -r requirements.txt
python manage.py migrate

:: 1. Export everything from your local SQLite database
python -Xutf8 manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e admin.logentry -e sessions --indent 1 -o data.json

:: 2. Point this window at Neon and Cloudinary (only this window, until you close it)
set DATABASE_URL=postgresql://...your Neon string...
set CLOUDINARY_URL=cloudinary://...your Cloudinary string...

:: 3. Create the tables in Neon, load the data, and upload the photos
python manage.py migrate
python -Xutf8 manage.py loaddata data.json
python manage.py move_media_to_cloud
```

**PowerShell:** the same commands, but set the variables like this:
```powershell
$env:DATABASE_URL = "postgresql://..."
$env:CLOUDINARY_URL = "cloudinary://..."
```

What you should see:
- `loaddata` prints `Installed N object(s) from 1 fixture(s)`.
- `move_media_to_cloud` prints `Uploaded N, already on Cloudinary 0, missing locally K.` "Missing locally" means a row points to a photo file that isn't on your PC. That's harmless, because the photo was already gone.

To preview what would be uploaded first, run `python manage.py move_media_to_cloud --dry-run`. Running it twice is safe: photos that are already uploaded are skipped.

Afterwards, delete `data.json`. It contains every member's email and password hash.

> `-Xutf8` stops Windows from breaking Bangla text during export and import. Don't leave it out.

## Step 6. Deploy

On Render, click **Manual Deploy → Deploy latest commit**. Near the end of the build log you'll see a checklist:

```
== Launch check ==
OK   Debug mode is off
OK   Database is PostgreSQL (now: postgresql)
OK   Uploaded photos are stored permanently
OK   Email is configured
OK   There is an admin who can approve members (1)
TODO Only one committee session is current (2019, 2020, 2021, 2025/2026)
      -> In Admin panel > Committee and admins, move old sessions to past. ...
1 item(s) left. See DEPLOY.md.
```

Anything marked **TODO** is something left to do. The build doesn't fail because of it.

## Step 7. Final checks on the live site

1. Log in with `DJANGO_ADMIN_EMAIL`.
2. **Admin panel → Committee and admins**: move old sessions to *past*, so that only this year's session is current. The current President, GS and AGS get admin powers automatically.
3. Upload a profile photo, then use **Manual Deploy** again. The photo must still be there after the deploy.
4. Log out, click **Forgot password**, and confirm that the email arrives (check Spam the first time).
5. Register a test account, approve it in the **Admin panel**, confirm the approval email arrives, then delete the test account.

## Optional: stop the site from sleeping

A free Render site sleeps after 15 idle minutes, and the next visitor waits about a minute. To keep it awake:

1. Create a free account at <https://uptimerobot.com>.
2. Add an **HTTP(s)** monitor for `https://<your-site>.onrender.com/healthz/` with a **5-minute** interval.

One always-awake site uses about 744 of Render's 750 free hours a month, so this only works if this is your **only** free Render service. Neon's database also sleeps on its own after 5 idle minutes and wakes in under a second. Within the free plan's monthly compute allowance, it stays free.

---

## If something goes wrong

| Problem | Fix |
|---|---|
| Build log: `DJANGO_SECRET_KEY must be set` | Add `DJANGO_SECRET_KEY` in Environment. |
| Build log: `could not translate host name` or `password authentication failed` | The `DATABASE_URL` is mistyped. Copy it again from Neon. |
| `loaddata` says `duplicate key value` | The Neon database already has data. In Neon, create a fresh branch or database, update `DATABASE_URL`, and run step 5 again. |
| Photos are broken after deploy | Check that `CLOUDINARY_URL` is set on Render and that you ran `move_media_to_cloud`. |
| Emails don't arrive | Make sure `EMAIL_HOST_PASSWORD` is the **app password**, not your Gmail password, and that `DJANGO_EMAIL_BACKEND` is the SMTP one. |
| Locked out of admin | Set `DJANGO_ADMIN_EMAIL` to your account and redeploy. It becomes an active admin again. To reset the password, temporarily change `DJANGO_ADMIN_EMAIL` to a new address and set a new password. That creates a second admin you can use to fix the first. |
