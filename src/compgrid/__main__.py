from . import compgrid, snowflake


TARGETS = {
    "email": compgrid.email,
    "slack": compgrid.slack,
    "slackimg": compgrid.slackimg,
}


if __name__ == "__main__":
    import argparse
    import pathlib

    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=TARGETS.keys())
    parser.add_argument("config")
    args = parser.parse_args()

    connection = snowflake.get_engine()
    target_function = TARGETS[args.target]
    target_function(connection, args.config)
