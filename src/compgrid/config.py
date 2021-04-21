import io
import numbers
from datetime import datetime, timedelta
import pathlib
import re
import yaml
from yaml.loader import SafeLoader
import urllib.parse

import pandas as pd
from PIL import Image, ImageDraw


def calculate_total_over(df):
    """If df represents a fraction, calculate it, handling edge cases correctly"""
    total = df["total"]
    over = df.get("over")
    if over is None:
        return total
    elif over == 0:
        # division by zero
        return None
    return total / over


def style_positive_green(value):
    color = "#00b37d" if value >= 0 else "#f00"
    return f"color: {color}"


def style_negative_green(value):
    color = "#00b37d" if value <= 0 else "#f00"
    return f"color: {color}"


def style_neutral(value):
    return "color: #000"


STYLES = {
    "positive-green": style_positive_green,
    "negative-green": style_negative_green,
    "neutral": style_neutral,
}


class ConfigError(Exception):
    def __init__(self, message, line=0, filename=None):
        self.message = message
        self.line = line
        self.filename = filename
        super().__init__(self.message)

    def __str__(self):
        if self.filename is not None:
            return f"{self.filename}:{self.line}: {self.message}"
        return f"FILE:{self.line}: {self.message}"


class Row:
    def __init__(self, name, query, type, style=None, columns=None, fields=None):
        self.name = name
        self.query = query
        self.type = type
        self.style = style if style is not None else style_positive_green
        self.columns = columns if columns is not None else []
        self.fields = fields if fields is not None else {}


class Column:
    pass


class TrailingAverage(Column):
    def __init__(self, days=7):
        self.days = days

    def eval(self, df, today, row=None):
        df = df[
            (df.date < today) & (df.date >= today - timedelta(days=self.days))
        ].mean()
        return calculate_total_over(df)


class DaysAgo(Column):
    def __init__(self, days=7):
        self.days = days

    def eval(self, df, today, row=None):
        df = df[df.date == today - timedelta(days=self.days)].sum()
        return calculate_total_over(df)


class WeekdayWeekend(Column):
    def __init__(self, days=7):
        self.days = days

    def eval(self, df, today, row=None):
        start_date = end_date = today - timedelta(days=self.days)
        if end_date.weekday() >= 5:
            # if Saturday or Sunday then count the entire Fri-Sun weekend
            start_date = end_date - timedelta(days=end_date.weekday() - 4)
        df = df[(df.date >= start_date) & (df.date <= end_date)].sum()
        return calculate_total_over(df)


class Month(Column):
    def __init__(self, months_ago=1):
        self.months_ago = months_ago

    def eval(self, df, today, row=None):
        # XXX[marek] correct for today being actually yesterday
        new_month = today.month - self.months_ago
        new_year = today.year
        while new_month < 1:
            new_month += 12
            new_year -= 1

        month_start = today.replace(year=new_year, month=new_month, day=1)
        month_end = (month_start + timedelta(days=31)).replace(day=1) - timedelta(
            days=1
        )

        df = df[(df.date <= month_end) & (df.date >= month_start)].sum()
        return calculate_total_over(df)


class MonthAgo(Column):
    def __init__(self, months_ago=1):
        self.months_ago = months_ago

    def eval(self, df, today, row=None):
        new_month = today.month - self.months_ago
        new_year = today.year
        while new_month < 1:
            new_month += 12
            new_year -= 1

        extra_days = 0
        while True:
            try:
                target = today.replace(
                    year=new_year, month=new_month, day=today.day - extra_days
                )
                break
            except ValueError:
                extra_days += 1

        df = df[df.date == target].sum()
        return calculate_total_over(df)


class WeeksAgo(Column):
    def __init__(self, weeks_ago=0):
        self.weeks_ago = weeks_ago

    def eval(self, df, today, row=None):
        # XXX[marek] correct for today being actually yesterday
        today = today + timedelta(days=1)
        week_start = today - timedelta(days=today.weekday())
        # TODO[marek] decide if first day of the week is Sunday or Monday
        # week_start = today - timedelta(days=(today.weekday() + 1) % 7)
        week_start = week_start - timedelta(days=7 * self.weeks_ago)
        week_end = week_start + timedelta(days=6)

        df = df[(df.date <= week_end) & (df.date >= week_start)].sum()
        return calculate_total_over(df)


class WeekToDate(Column):
    def __init__(self, weeks_ago=0):
        self.weeks_ago = weeks_ago

    def eval(self, df, today, row=None):
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start - timedelta(days=7 * self.weeks_ago)
        today = today - timedelta(days=7 * self.weeks_ago)

        df = df[(df.date <= today) & (df.date >= week_start)].sum()
        return calculate_total_over(df)


class MonthToDate(Column):
    def __init__(self, months_ago=0):
        self.months_ago = months_ago

    def eval(self, df, today, row=None):
        new_month = today.month - self.months_ago
        new_year = today.year
        while new_month < 1:
            new_month += 12
            new_year -= 1

        extra_days = 0
        while True:
            try:
                target = today.replace(
                    year=new_year, month=new_month, day=today.day - extra_days
                )
                break
            except ValueError:
                extra_days += 1

        month_start = target.replace(day=1)

        df = df[(df.date <= target) & (df.date >= month_start)].sum()
        return calculate_total_over(df)


class MonthToDateAverage(Column):
    def __init__(self, months_ago=0):
        self.months_ago = months_ago

    def eval(self, df, today, row=None):
        month_start = today.replace(day=1)
        for _ in range(self.months_ago):
            month_start = (month_start - timedelta(days=1)).replace(day=1)
            today = today.replace(month=month_start.month, year=month_start.year)

        df = df[(df.date <= today) & (df.date >= month_start)].mean()
        return calculate_total_over(df)


class SinceDate(Column):
    def __init__(self, since=None):
        if since is None:
            since = datetime.date(2000, 1, 1)
        self.since = since

    def eval(self, df, today, row=None):
        df = df[(df.date <= today) & (df.date >= self.since)].sum()
        return calculate_total_over(df)


class NumberGoal(Column):
    def __init__(self, number):
        self.number = number

    def eval(self, df, today, row=None):
        return self.number


class FieldGoal(Column):
    def __init__(self, field_name):
        self.field_name = field_name

    def eval(self, df, today, row=None):
        if row is None:
            return None

        value = row.fields.get(self.field_name)
        if value is None:
            return None
        if isinstance(value, numbers.Number):
            return value

        # if field value is not a number, interpret it as query path
        query_path = pathlib.Path(value)
        if not query_path.is_absolute():
            # If a relative path, interpret it relative to the config file
            query_path = row.config_directory / query_path
        sql = query_path.read_text()
        df = pd.read_sql_query(sql, row.connection)
        return calculate_total_over(df.sum())


class SparklineColumn:
    def __init__(self, name, days=30):
        self.name = name
        self.template = "column_sparkline.md"
        self.days = days

    @classmethod
    def from_config(cls, config):
        name = config.get("name")
        days = config.get("days", 30)
        return cls(name, days)

    def plot_sparkline(self, df):
        results = df.values.tolist()
        min_value, max_value = df.min(), df.max()
        result_range = max(max_value - min_value, 1 / 20)

        im = Image.new("RGBA", (len(results) + 2, 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)

        # TODO[marek]: do not draw lines between dates with no values
        coords = []
        for x, y in enumerate(results):
            if not pd.isna(y):
                coords.append((x, 20 - (y - min_value) / result_range * 20))
        draw.line(coords, fill="#000000")

        if len(coords) > 0:
            end = coords[-1]
            draw.rectangle(
                [end[0] - 1, end[1] - 1, end[0] + 1, end[1] + 1], fill="#FF0000"
            )

        del draw

        f = io.BytesIO()
        im.save(f, "PNG")
        return urllib.parse.quote(f.getvalue())

    def eval(self, df, today, row=None):
        days = pd.date_range(start=today - timedelta(days=self.days), end=today)
        df = df[(df.date <= today) & (df.date >= today - timedelta(days=self.days))]
        df = df.set_index("date").reindex(days)
        if "over" in df:
            return self.plot_sparkline(df["total"] / df["over"])
        return self.plot_sparkline(df["total"])

    def __repr__(self):
        return "SparklineColumn(%r, %r)" % (self.name, self.days)


class NumberColumn:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.template = "column_number.md"

    @classmethod
    def from_config(cls, config):
        line = config["__line__"]
        if "name" not in config:
            raise ConfigError("missing name attribute for column", line=line)
        if "value" not in config:
            raise ConfigError("missing value attribute for column", line=line)
        return cls(config["name"], read_column_value_config(config["value"], line=line))

    def eval(self, dt, today, row=None):
        return self.value.eval(dt, today, row)

    def __repr__(self):
        return "NumberColumn(%r, %r)" % (self.name, self.value)


class PctChangeColumn:
    def __init__(self, name, value, base):
        self.name = name
        self.value = value
        self.base = base
        self.template = "column_pctchange.md"

    @classmethod
    def from_config(cls, config):
        line = config["__line__"]
        if "name" not in config:
            raise ConfigError("missing name attribute for column", line=line)
        if "value" not in config:
            raise ConfigError("missing value attribute for column", line=line)
        if "base" not in config:
            raise ConfigError("missing base attribute for column", line=line)
        return cls(
            config["name"],
            read_column_value_config(config["value"], line=line),
            read_column_value_config(config["base"], line=line),
        )

    def eval(self, dt, today, row=None):
        value = self.value.eval(dt, today, row)
        base = self.base.eval(dt, today, row)
        if value is None or base is None:
            return None
        elif base == 0 and value == 0:
            return 0.0
        elif base == 0:
            return None
        return 100.0 * value / base - 100.0

    def __repr__(self):
        return "PctChangeColumn(%r, %r, %r)" % (self.name, self.value, self.base)


class SafeLineLoader(SafeLoader):
    "Attach line numbers to every mapping node in YAML."

    def construct_mapping(self, node, deep=False):
        mapping = super(SafeLineLoader, self).construct_mapping(node, deep=deep)
        # Add 1 so line numbering starts at 1
        mapping["__line__"] = node.start_mark.line + 1
        return mapping


def read_column_value_config(text, line=0):
    if text == "yesterday":
        return DaysAgo(0)
    elif text == "weekdayweekend":
        return WeekdayWeekend(0)
    elif (m := re.match(r"daysago\((\d+)\)", text)) is not None:
        return DaysAgo(int(m.group(1)))
    elif text == "lastweek":
        return WeeksAgo(1)
    elif (m := re.match(r"week\((\d+)\)", text)) is not None:
        return WeeksAgo(int(m.group(1)))
    elif (m := re.match(r"trailingavg\((\d+)\)", text)) is not None:
        return TrailingAverage(int(m.group(1)))
    elif text == "month":
        return Month()
    elif (m := re.match(r"month\((\d+)\)", text)) is not None:
        return Month(int(m.group(1)))
    elif text == "monthago":
        return MonthAgo()
    elif (m := re.match(r"monthago\((\d+)\)", text)) is not None:
        return MonthAgo(int(m.group(1)))
    elif text == "wtd":
        return WeekToDate()
    elif (m := re.match(r"wtd\((\d+)\)", text)) is not None:
        return WeekToDate(int(m.group(1)))
    elif text == "mtdavg":
        return MonthToDateAverage()
    elif (m := re.match(r"mtdavg\((\d+)\)", text)) is not None:
        return MonthToDateAverage(int(m.group(1)))
    elif text == "mtd":
        return MonthToDate()
    elif (m := re.match(r"mtd\((\d+)\)", text)) is not None:
        return MonthToDate(int(m.group(1)))
    elif (m := re.match(r"since\((\d\d\d\d-\d\d-\d\d)\)", text)) is not None:
        since = datetime.strptime(m.group(1), "%Y-%m-%d")
        return SinceDate(since.date())
    elif (m := re.match(r"goal\((\d+)\)", text)) is not None:
        return NumberGoal(m.group(1))
    elif (m := re.match(r"goal\(([^)]+)\)", text)) is not None:
        return FieldGoal(m.group(1))
    else:
        raise ConfigError("unknown column value '%s'" % text, line=line)


def read_column_config(config):
    parsed = []
    for column in config:
        if "type" not in column:
            raise ConfigError(
                "missing type attribute for column", line=column["__line__"]
            )
        type_ = column["type"]
        if type_ == "number":
            parsed.append(NumberColumn.from_config(column))
        elif type_ == "pctchange":
            parsed.append(PctChangeColumn.from_config(column))
        elif type_ == "sparkline":
            parsed.append(SparklineColumn.from_config(column))
        else:
            raise ConfigError(
                "unknown column type '%s'" % type_, line=column["__line__"]
            )

    return parsed


def read_row_config(config):
    parsed = []
    for row in config:
        if "name" not in row:
            raise ConfigError("missing name attribute for row", line=row["__line__"])
        if "query" not in row:
            raise ConfigError("missing query attribute for row", line=row["__line__"])
        type_ = row["type"] if "type" in row else "float"
        if type_ not in ["number", "float", "percent", "currency"]:
            raise ConfigError("unknown row type '%s'" % type_, line=row["__line__"])
        style_name = row["style"] if "style" in row else "positive-green"
        try:
            style = STYLES[style_name]
        except KeyError:
            raise ConfigError(
                "unknown row style '%s'" % style_name, line=row["__line__"]
            )
        parsed.append(
            Row(
                name=row["name"],
                query=row["query"],
                style=style,
                type=type_,
                fields=row,
            )
        )
    return parsed


def read_config(path):
    path = pathlib.Path(path)
    config_directory = path.parent
    # Read the config data as YAML
    with open(path) as infile:
        config = read_config_from_string(infile, filename=path)

    # Read the query files and add then to the config data
    for row in config["rows"]:
        query_path = pathlib.Path(row.query)
        if not query_path.is_absolute():
            # If a relative path, interpret it relative to the config file
            query_path = config_directory / query_path
        row.query = query_path.read_text()
        row.config_directory = config_directory

    return config


def read_config_from_string(s, filename="STREAM"):
    try:
        config = yaml.load(s, Loader=SafeLineLoader)

        if "name" not in config:
            raise ConfigError("missing toplevel name attribute", line=1)
        if "columns" not in config:
            raise ConfigError("missing toplevel columns attribute", line=1)
        if not isinstance(config["columns"], list):
            raise ConfigError("columns must be a list", line=1)

        config["columns"] = read_column_config(config["columns"])

        if "rows" in config:
            if not isinstance(config["rows"], list):
                raise ConfigError("rows must be a list", line=1)

        config["rows"] = read_row_config(config["rows"])

    except ConfigError as e:
        e.filename = filename
        raise
    return config
