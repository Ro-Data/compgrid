import unittest

from .config import read_config_from_string, ConfigError


class TestReadConfig(unittest.TestCase):
    def test_missing_name(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
columns:
- name: overall
  type: number
  value: since(2000-01-01)
- name: last week
  type: number
  value: lastweek
"""
            )

    def test_missing_columns(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
rows:
  - name: Email sends
    query: sql/thealth/email_sends.sql
    type: number
"""
            )

        self.assertEqual(cm.exception.message, "missing toplevel columns attribute")
        self.assertEqual(cm.exception.line, 1)

    def test_columns_not_a_list(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
columns: this won't work
"""
            )

        self.assertEqual(cm.exception.message, "columns must be a list")
        self.assertEqual(cm.exception.line, 1)

    def test_missing_column_name(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
columns:
- type: number
  value: since(2000-01-01)
- name: last week
  type: number
  value: lastweek
"""
            )

        self.assertEqual(cm.exception.message, "missing name attribute for column")
        self.assertEqual(cm.exception.line, 3)

    def test_missing_column_value(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
columns:
- name: number
  type: number
  value: since(2000-01-01)
- name: last week
  type: number
"""
            )

        self.assertEqual(cm.exception.message, "missing value attribute for column")
        self.assertEqual(cm.exception.line, 6)

    def test_missing_column_type(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
columns:
- name: number
  value: since(2000-01-01)
- name: last week
  type: number
  value: lastweek
"""
            )

        self.assertEqual(cm.exception.message, "missing type attribute for column")
        self.assertEqual(cm.exception.line, 3)

    def test_unknown_column_type(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
# columns define the columns of the comparison grid
columns:
- name: overall # show the result of the query as number
  type: number
  value: since(2000-01-01) # value to show
- name: last week
  type: number
  value: lastweek
- name: week over week
  type: unknown
  value: lastweek
  base: week(2)
"""
            )

        self.assertEqual(cm.exception.message, "unknown column type 'unknown'")
        self.assertEqual(cm.exception.line, 10)

    def test_unknown_column_value(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
# columns define the columns of the comparison grid
columns:
- name: overall # show the result of the query as number
  type: number
  value: after(2000-01-01) # value to show
- name: last week
  type: number
  value: lastweek
"""
            )

        self.assertEqual(
            cm.exception.message, "unknown column value 'after(2000-01-01)'"
        )
        self.assertEqual(cm.exception.line, 4)

    def test_rows_not_a_list(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
columns:
- name: yesterday
  type: number
  value: yesterday
rows: this won't work
"""
            )

        self.assertEqual(cm.exception.message, "rows must be a list")
        self.assertEqual(cm.exception.line, 1)

    def test_unknown_row_type(self):
        with self.assertRaises(ConfigError) as cm:
            c = read_config_from_string(
                """\
name: thealth
columns:
- name: yesterday
  type: number
  value: yesterday
rows:
  - name: Email sends
    query: sql/thealth/email_sends.sql
    type: unknown
"""
            )

        self.assertEqual(cm.exception.message, "unknown row type 'unknown'")
        self.assertEqual(cm.exception.line, 7)
