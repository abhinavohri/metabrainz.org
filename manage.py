# CLI entrypoint for local development, database setup, maintenance jobs, and
# translation catalog generation. The Docker development wrapper calls into this
# file via `./develop.sh manage ...`.
from werkzeug.serving import run_simple
from metabrainz import db
from metabrainz import create_app
from metabrainz.model.access_log import AccessLog
from metabrainz.invoices.send_invoices import QuickBooksInvoiceSender
import urllib.parse
import subprocess
import os
import click

import logging

from metabrainz.supporter.copy_mb_row_ids import copy_row_ids

# SQL scripts are kept separate from Python so the database schema can be
# initialized in the same order in development and tests.
ADMIN_SQL_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'admin', 'sql')

# Click command group exposed at the bottom of this file.
cli = click.Group()

# Build the main Flask application once for commands that can reuse shared
# configuration and extension setup.
application = create_app()


@cli.command()
@click.option("--host", "-h", default="0.0.0.0", show_default=True)
@click.option("--port", "-p", default=8080, show_default=True)
@click.option("--debug", "-d", is_flag=True,
              help="Turns debugging mode on or off. If specified, overrides "
                   "'DEBUG' value in the config file.")
def runserver(host, port, debug=False):
    """Run the development server without going through Docker Compose."""
    run_simple(
        hostname=host,
        port=port,
        application=application,
        use_debugger=debug,
        use_reloader=debug,
    )


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Drop existing database and user.")
@click.option("--create-db", "-c", is_flag=True, help="Create database and extensions.")
def init_db(force=False, create_db=False):
    """Initialize the local database schema from the SQL files in admin/sql."""
    # Administrative operations, such as creating or dropping the database,
    # connect through the configured Postgres admin URI first.
    db.init_db_engine(application.config["POSTGRES_ADMIN_URI"])

    if force:
        # This is intentionally gated behind --force because it drops data.
        click.echo('Dropping existing database... ', nl=False)
        db.run_sql_script_without_transaction(os.path.join(ADMIN_SQL_DIR, 'drop_db.sql'))
        click.echo('Done.')

    if create_db:
        # Database/user creation and extensions must happen outside the normal
        # application database connection.
        click.echo('Creating user and a database... ', nl=False)
        db.run_sql_script_without_transaction(os.path.join(ADMIN_SQL_DIR, 'create_db.sql'))
        click.echo('Done.')

        click.echo('Creating database extensions... ', nl=False)
        db.run_sql_script_without_transaction(os.path.join(ADMIN_SQL_DIR, 'create_extensions.sql'))
        click.echo('Done.')

    # Switch to the application database before creating schema objects.
    db.init_db_engine(application.config["SQLALCHEMY_DATABASE_URI"])

    # Types must exist before tables that reference them.
    click.echo('Creating types... ', nl=False)
    db.run_sql_script(os.path.join(ADMIN_SQL_DIR, 'create_types.sql'))
    click.echo('Done.')

    # OAuth tables live in a separate SQL file but share the same database.
    click.echo('Creating tables... ', nl=False)
    db.run_sql_script(os.path.join(ADMIN_SQL_DIR, 'create_tables.sql'))
    db.run_sql_script(os.path.join(ADMIN_SQL_DIR, 'oauth', 'create_tables.sql'))
    click.echo('Done.')

    click.echo('Creating primary and foreign keys... ', nl=False)
    db.run_sql_script(os.path.join(ADMIN_SQL_DIR, 'create_primary_keys.sql'))
    db.run_sql_script(os.path.join(ADMIN_SQL_DIR, 'create_foreign_keys.sql'))
    click.echo('Done.')

    click.echo('Creating indexes... ', nl=False)
    db.run_sql_script(os.path.join(ADMIN_SQL_DIR, 'create_indexes.sql'))
    click.echo('Done.')

    click.echo("Database has been initialized successfully!")


@cli.command()
def extract_strings():
    """Extract all strings into messages.pot.
    This command should be run after any translatable strings are updated.
    Otherwise updates are not going to be available on Weblate.
    """
    # Scan both Flask apps plus the React source. React uses gettext("...")
    # calls so its strings land in the same PO catalog as Jinja/Python.
    _run_command("pybabel extract -F metabrainz/babel.cfg "
                 "-o metabrainz/messages.pot "
                 "metabrainz/ oauth/ frontend/js/src/")
    click.echo("Strings have been successfully extracted into messages.pot file.")


@cli.command()
def compile_translations():
    """Compile translations for use."""
    # Flask-Babel reads compiled .mo files at runtime.
    _run_command("pybabel compile -d metabrainz/translations")
    click.echo("Translated strings have been compiled and ready to be used.")


@cli.command()
def cleanup_logs():
    """Remove stale access-log IP address records."""
    # Use a fresh app context so scheduled/manual runs do not depend on a
    # request context.
    with create_app().app_context():
        AccessLog.remove_old_ip_addr_records()


@cli.command()
def send_invoices():
    """ Send invoices that are prepared, but unsent in QuickBooks."""

    # QuickBooks integration expects Flask config and database access.
    with create_app().app_context():
        qb = QuickBooksInvoiceSender()
        qb.send_invoices()


@cli.command()
def send_invoice_reminders():
    """ Send invoices reminders about invoices that remain unpaid."""

    # Invoice reminder runs are rare/manual enough that verbose logging is
    # useful for diagnosing QuickBooks or mail delivery failures.
    logging.getLogger().setLevel(logging.DEBUG)
    with create_app().app_context():
        qb = QuickBooksInvoiceSender()
        qb.send_invoice_reminders()


@cli.command()
def import_musicbrainz_row_ids():
    """ Import musicbrainz row ids for users """
    # Backfill local supporter rows with MusicBrainz row IDs.
    with create_app().app_context():
        copy_row_ids()


def _run_psql(script, uri, database=None):
    """Run one raw SQL file through the psql command-line client."""
    # Some database bootstrap actions cannot run through SQLAlchemy because
    # they need to happen before the application database exists.
    hostname, port, db_name, username, password = _explode_db_uri(uri)
    script = os.path.join(ADMIN_SQL_DIR, script)
    command = [
        'psql',
        '-h', hostname,
        '-p', str(port),
        '-U', username,
        '-f', script,
    ]
    if database:
        # Allow callers to override the database parsed from the URI, for
        # example when connecting to the default postgres database.
        command.extend(['-d', database])
    return subprocess.call(command)


def _run_command(command):
    """Run a shell command and fail the invoking CLI command if it fails."""
    return subprocess.check_call(command, shell=True)


def _explode_db_uri(uri):
    """Extracts database connection info from the URI.
    Returns hostname, database name, username and password.
    """
    # SQLAlchemy-style database URIs need to be decomposed for psql arguments.
    uri = urllib.parse.urlsplit(uri)
    return uri.hostname, uri.port, uri.path[1:], uri.username, uri.password


if __name__ == '__main__':
    # Dispatch to the Click command group when the file is executed directly.
    cli()

"""
Example SQL kept here for manual local tier setup/debugging.
insert into tier (name, short_desc, long_desc, price, available, "primary") values ('We will contribute, we promise!', 'For lame user lying about supporting us.', 'Whatevs, you dont care anyway.', 0.0, 't', 't');
"""
