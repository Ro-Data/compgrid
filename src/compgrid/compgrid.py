import json
import os
import subprocess
import tempfile

import yagmail
from slack_sdk import WebClient
import structlog
import pandas as pd
from datetime import datetime, timedelta
from jinja2 import Environment, ChoiceLoader, FileSystemLoader, select_autoescape

from .config import read_config, ConfigError


log = structlog.get_logger()


class Row:
    def __init__(self, name, columns):
        self.name = name
        self.columns = columns


class ColumnValue:
    def __init__(self, name, template, value, type):
        self.name = name
        self.template = template
        self.value = value
        self.type = type

    def abs_value(self):
        if self.value is None:
            # TODO[marek]: return none?
            return 0
        return abs(self.value)

    def formatted_value(self):
        if self.value is None:
            return ""
        if self.type == "number":
            return f"{self.value:,.0f}"
        elif self.type == "percent":
            return f"{self.value * 100.0:,.2f}%"
        elif self.type == "currency":
            return f"${self.value:,.2f}"
        else:
            return f"{self.value:,.2f}"


def evaluate_row(row, config, connection):
    yesterday = datetime.date(datetime.now()) - timedelta(days=1)

    # TODO[marek]: pass connection to eval or make global
    row.connection = connection

    log.info("evaluating row", row=row.name)

    df = pd.read_sql_query(row.query, connection)
    columns = config["columns"]

    results = []
    for column in columns:
        result = column.eval(df, yesterday, row=row)
        results.append(
            ColumnValue(
                name=column.name, template=column.template, value=result, type=row.type
            )
        )

    row.columns = results
    return row


def build_message(config, connection):
    yesterday_date = datetime.date(datetime.now()) - timedelta(days=1)

    for k, v in config.items():
        if k == "__line__":
            continue
        if k not in ["columns", "rows"]:
            config[k] = v.format(yesterday_date=yesterday_date)

    results = []
    for row in config["rows"]:
        data = evaluate_row(row, config, connection)
        results.append(data)

    config["table"] = results
    config["yesterday_date"] = yesterday_date

    return config


def slack(connection, config):
    try:
        c = read_config(config)
    except ConfigError as e:
        log.exception("error reading config", error=str(e))
        return

    output = build_message(c, connection)

    env = Environment(
        loader=ChoiceLoader(
            [
                FileSystemLoader(
                    os.path.dirname(config) + "/templates/slack/" + c["name"]
                ),
                FileSystemLoader(os.path.dirname(config) + "/templates/slack"),
                FileSystemLoader(os.path.dirname(config) + "/templates"),
            ]
        )
    )

    template = env.get_template("slack.md")
    markdown = template.render(output)

    # Need to deal with Slack 3000 markdown limit per block
    parts = markdown.split("\n--\n")
    blocks = []
    for i, p in enumerate(parts):
        if i != 0:
            blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": p}})

    slack_token = os.getenv("SLACK_BOT_ACCESS_TOKEN")
    client = WebClient(token=slack_token)
    r = client.chat_postMessage(channel=f"#{c['slack']}", blocks=blocks)


def slackimg(connection, config):
    try:
        c = read_config(config)
    except ConfigError as e:
        log.exception("error reading config", error=str(e))
        return

    output = build_message(c, connection)

    env = Environment(
        loader=ChoiceLoader(
            [
                FileSystemLoader(
                    os.path.dirname(config) + "/templates/email/" + c["name"]
                ),
                FileSystemLoader(os.path.dirname(config) + "/templates/email"),
                FileSystemLoader(os.path.dirname(config) + "/templates"),
            ]
        )
    )

    def image_path(p):
        return os.path.join(os.path.dirname(os.path.abspath(config)), p)

    output["image"] = image_path

    template = env.get_template("body.html")
    body = template.render(output)

    if "header" in output:
        text_template = env.get_template("text.md")
        text = text_template.render(output)
    else:
        text = ""

    with tempfile.NamedTemporaryFile(suffix=".png") as tmpimg:
        subprocess.run(
            [
                "/usr/local/bin/wkhtmltoimage",
                "--allow",
                os.path.dirname(config),
                "-",
                tmpimg.name,
            ],
            input=body.encode("utf-8"),
        )

        log.info("sending to slack", channel=c["slack"])
        slack_token = os.getenv("SLACK_BOT_ACCESS_TOKEN")
        client = WebClient(token=slack_token)
        r = client.files_upload(
            channels=f"#{c['slack']}", file=tmpimg.name, filename=f"#{c['name']}.png"
        )

        if text:
            message_info = r.data["file"]["shares"]["public"]
            channel_id = r.data["file"]["channels"][0]
            ts = message_info[channel_id][0]["ts"]
            client.chat_update(
                channel=channel_id,
                ts=ts,
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
            )


def email(connection, config):
    try:
        c = read_config(config)
    except ConfigError as e:
        log.exception("error reading config", error=str(e))
        return

    output = build_message(c, connection)

    env = Environment(
        loader=ChoiceLoader(
            [
                FileSystemLoader(
                    os.path.dirname(config) + "/templates/email/" + c["name"]
                ),
                FileSystemLoader(os.path.dirname(config) + "/templates/email"),
                FileSystemLoader(os.path.dirname(config) + "/templates"),
            ]
        )
    )

    def image_path(p):
        return os.path.join(os.path.dirname(os.path.abspath(config)), p)

    output["image"] = image_path

    template = env.get_template("email.html")
    body = template.render(output)
    title = c["title"] if "title" in c else c["name"]
    recipients = c["email"].split(",")

    oauth2_file = os.path.expanduser("~/.oauth2_creds.json")
    if os.path.exists(oauth2_file):
        log.info("using oauth2 email credentials from file", path=oauth2_file)
        yag = yagmail.SMTP(oauth2_file=oauth2_file)
    elif os.environ.get("DATA_EMAIL_USER") and os.environ.get("DATA_EMAIL_PASSWORD"):
        log.info("using email credentials from environment")
        yag = yagmail.SMTP(
            user=os.environ["DATA_EMAIL_USER"],
            password=os.environ["DATA_EMAIL_PASSWORD"],
        )
    else:
        log.info("no email credentials found")
        return

    log.info("sending to email", recipients=",".join(recipients))
    yag.send(recipients, title, body)
