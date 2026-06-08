# Cited — signup page (`web/`)

A single static page (`index.html`) that introduces Cited and collects email signups
for the daily brief. No build step, no server.

## What it does today
- Shows the brand, the promise, and a signup form.
- **Not yet connected to anything.** Submitting just shows a local "you're on the list"
  message so the page is testable. Emails are NOT stored until you do step 2 below.

## To make it live (about 30 minutes, mostly free)

**1. Pick a free email tool** (any one gives you a hosted signup form):
   beehiiv, Substack, ConvertKit, or Buttondown. Create the account and a publication.

**2. Connect the form.** In the email tool, find the *embed form* / *form action URL*.
   Open `index.html`, find:
   ```html
   <form id="signup" action="" method="post" novalidate>
   ```
   Put your tool's URL inside the quotes, e.g. `action="https://your-tool.com/subscribe"`.
   (That's the only edit needed; the demo-mode script then steps aside automatically.)

**3. Put the page online** (free), pick one:
   - **GitHub Pages:** repo settings → Pages → deploy from `main`, folder `/web`.
   - **Netlify / Vercel:** drag the `web/` folder onto their dashboard.
   - Later: point your own domain at it.

## How the daily brief connects
The engine writes `data/brief_<date>.html` every run (branded, email-ready). That HTML is
what the email tool sends to the list.
