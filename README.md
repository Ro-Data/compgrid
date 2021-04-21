# Metric Comparison Grids

Framework to generate and send defined comparison grids to selected recipients.

```bash
# Send to slack
# Export access token for slack integration
export SLACK_BOT_ACCESS_TOKEN=xoxb-
python -m compgrid slackimg config.yml

# Send to email
export DATA_EMAIL_USER=your_email
export DATA_EMAIL_PASSWORD=your_password
python -m compgrid email config.yml
```

If you use a 2-Factor Authentication in GMail, you'll need set up an App Password in your Google Account and use it instead of your regular password. Here are the steps for setting this up:

- [Go to your Google Account](https://myaccount.google.com/)
- Click on the Security tab.
- Scroll down to "Signing in to Google" and turn on 2-Step Verification.
- Click on App Passwords and under "Select app", type in "compgrid."
- Copy and paste the new app password under `export DATA_EMAIL_PASSWORD=your_app_password`

## Installation

```bash
git clone git@github.com:Ro-Data/compgrid.git compgrid
cd compgrid && pip install .
```

## Configuration

Each comparison grid is defined by a single [YAML](http://yaml.org) file:

```yaml
name: care-metrics
slack: care-metrics-report # slack channels to send report to
email: patient-care@ro.co # email-addresses to send report to
columns: # columns of the grid are defined by time series calculation
- name: yesterday
  type: number # show the result of the query as number
  value: yesterday # value to show
- name: vs 7 days ago
  type: pctchange # show % change over time
  value: yesterday # value to compare
  base: daysago(7) # base value
- name: vs a month ago
  type: pctchange
  value: yesterday
  base: monthsago(1)
- name: vs trailing 7-day average
  type: pctchange
  value: yesterday
  base: trailingavg(7)
- name: last 7 days
  type: number
  value: trailingsum(7)
- name: vs prior 7 days
  type: pctchange
  value: trailingsum(7)
  base: trailingsum(14, 7)
rows: # rows of the grid are defined by SQL queries
- name: Total Zendesk Tickets
  query: sql/patient-care/total_zendesk_tickets.sql
  type: number
- name: CSAT Score
  query: sql/patient-care/csat_score.sql
  type: percent
  goal: 90
# all other settings are passed directly into Jinja template
header: "Care team flash for {yesterday} :telephone-receiver::computer::mail:"
footer: "Take Care! :wave:"
```

### Row definitions

Each row of the grid defines a SQL query to run and a format to display it as:

```yaml
- name: Total Zendesk Tickets
  query: sql/patient-care/total_zendesk_tickets.sql
  type: number
```

SQL query should return have `date` and `total` columns, one row per day:

```sql
select date, count(distinct member_id) as total
from doctor_treatment_request
where condition_id = 33
group by date
```

If you return `date`, `total` and `over` columns, the framework will automatically calculate a fraction `total / over`:

```sql
select date,
    coalesce(sum(engagement.clicks), 0) as total,
    coalesce(sum(engagement.sends), 0) as over
from engagement
group by date
```

Following values are supported for `type`:

 - `float` - display as a decimal fraction (ie. 13.79)
 - `number` - display as whole number (ie. 13)
 - `percent` - display as percentage (ie. 1379%)
 - `currency` - display as currency (ie. $13.79)

### Column definitions

Each column of the grid defines a timeseries calculation to do on the results of the query in a row.

There are three supported types of columns: `number`, `pctchange` and `sparkline`.

`number` column displays the value calculated according to `value`:

```
- name: yesterday    # name of the column to display
  type: number       # show the result of the query as number
  value: yesterday   # value to show
```

`pctchange` column displays the difference between `base` and `value` as percent:

```yaml
- name: week over week
  type: pctchange
  value: lastweek
  base: week(2)
```

`sparkline` column displays a small graph of the past 30 days:

```yaml
- name: sparkline
  type: sparkline
```

Following values are supported for `value` and `base`:

 - `yesterday` - value as of yesterday
 - `daysago(N)` - value as calculated N days ago from yesterday
 - `lastweek` - value over the previous week
 - `week(N)` - value over the week N weeks ago
 - `trailingavg(N)` - average over N last days from yesterday
 - `monthago` - value as of the same day a month ago
 - `wtd` - value from start of current week to yesterday
 - `wtd(N)` - value from start of the week N weeks ago to the same day of the week as yesterday
 - `mtd` - value from start of current week to yesterday
 - `mtd(N)` - value from start of the month N months ago to the same day of the month as yesterday
 - `since(YYYY-MM-DD)` - value from date YYYY-MM-DD to yesterday

### Testing

We use [Tox](https://tox.readthedocs.io/) to automate testing:

```bash
cd compgrid && tox
```
