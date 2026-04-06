"""Command-line interface for querying the Interop DB Registry."""

import json
import sys

import click
from interopdb.client import DEFAULT_BASE_URL, InteropClient, InteropError


@click.group()
@click.option("--url", default=DEFAULT_BASE_URL, show_default=True, help="Interop DB server URL.")
@click.pass_context
def cli(ctx, url):
    """Query the Interop DB Registry."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = InteropClient(base_url=url)


@cli.command()
@click.argument("identifier")
@click.option("-o", "--output", type=click.Path(), help="Save result to a JSON file.")
@click.pass_context
def gene(ctx, identifier, output):
    """Query a gene by local ID or UID."""
    _query(ctx.obj["client"].get_gene, identifier, output)


@cli.command()
@click.argument("identifier")
@click.option("-o", "--output", type=click.Path(), help="Save result to a JSON file.")
@click.pass_context
def strain(ctx, identifier, output):
    """Query a strain by local ID or UID."""
    _query(ctx.obj["client"].get_strain, identifier, output)


@cli.command()
@click.argument("gene_id")
@click.argument("strain_id")
@click.option("-o", "--output", type=click.Path(), help="Save result to a JSON file.")
@click.pass_context
def pair(ctx, gene_id, strain_id, output):
    """Query a gene-strain pair across all source databases."""
    _query(lambda _=None: ctx.obj["client"].get_pair(gene_id, strain_id), None, output)


@cli.command(name="search-entities")
@click.argument("query", default="")
@click.option("-o", "--output", type=click.Path(), help="Save result to a JSON file.")
@click.pass_context
def search_entities(ctx, query, output):
    """Search entities by local ID, UID, or synonym."""
    _query(ctx.obj["client"].search_entities, query, output)


@cli.command(name="search-relationships")
@click.argument("query", default="")
@click.option("-o", "--output", type=click.Path(), help="Save result to a JSON file.")
@click.pass_context
def search_relationships(ctx, query, output):
    """Search gene-strain relationships by a gene or strain identifier."""
    _query(ctx.obj["client"].search_relationships, query, output)


def _query(func, identifier, output):
    try:
        result = func(identifier) if identifier is not None else func()
    except InteropError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)

    formatted = json.dumps(result, indent=2, ensure_ascii=False)

    if output:
        InteropClient.save_json(result, output)
        click.echo(f"Saved to {output}")
    else:
        click.echo(formatted)
