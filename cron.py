#!/usr/bin/env python3
#
# Copyright 2019 Miklos Vajna. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

"""The cron module allows doing nightly tasks."""

from typing import Any
import argparse
import datetime
import glob
import logging
import os
import subprocess
import time
import traceback
import urllib.error

import areas
import config
import overpass_query
import stats
import util


def get_date_prefix() -> str:
    """Generates the current date as a log prefix."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    """Wrapper around logging.info()."""
    logging.info(get_date_prefix() + " INFO " + msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    """Wrapper around logging.error()."""
    logging.error(get_date_prefix() + " ERROR" + msg, *args, **kwargs)


def overpass_sleep() -> None:
    """Sleeps to respect overpass rate limit."""
    while True:
        sleep = overpass_query.overpass_query_need_sleep()
        if not sleep:
            break
        info("overpass_sleep: waiting for %s seconds", sleep)
        time.sleep(sleep)


def should_retry(retry: int) -> bool:
    """Decides if we should retry a query or not."""
    return retry < 20


def update_osm_streets(relations: areas.Relations, update: bool) -> None:
    """Update the OSM street list of all relations."""
    for relation_name in relations.get_active_names():
        relation = relations.get_relation(relation_name)
        if not update and os.path.exists(relation.get_files().get_osm_streets_path()):
            continue
        info("update_osm_streets: start: %s", relation_name)
        retry = 0
        while should_retry(retry):
            if retry > 0:
                info("update_osm_streets: try #%s", retry)
            retry += 1
            try:
                overpass_sleep()
                query = relation.get_osm_streets_query()
                relation.get_files().write_osm_streets(overpass_query.overpass_query(query))
                break
            except urllib.error.HTTPError as http_error:
                info("update_osm_streets: http error: %s", str(http_error))
        info("update_osm_streets: end: %s", relation_name)


def update_osm_housenumbers(relations: areas.Relations, update: bool) -> None:
    """Update the OSM housenumber list of all relations."""
    for relation_name in relations.get_active_names():
        relation = relations.get_relation(relation_name)
        if not update and os.path.exists(relation.get_files().get_osm_housenumbers_path()):
            continue
        info("update_osm_housenumbers: start: %s", relation_name)
        retry = 0
        while should_retry(retry):
            if retry > 0:
                info("update_osm_housenumbers: try #%s", retry)
            retry += 1
            try:
                overpass_sleep()
                query = relation.get_osm_housenumbers_query()
                relation.get_files().write_osm_housenumbers(overpass_query.overpass_query(query))
                break
            except urllib.error.HTTPError as http_error:
                info("update_osm_housenumbers: http error: %s", str(http_error))
        info("update_osm_housenumbers: end: %s", relation_name)


def update_ref_housenumbers(relations: areas.Relations, update: bool) -> None:
    """Update the reference housenumber list of all relations."""
    for relation_name in relations.get_active_names():
        relation = relations.get_relation(relation_name)
        if not update and os.path.exists(relation.get_files().get_ref_housenumbers_path()):
            continue
        references = config.Config.get_reference_housenumber_paths()
        streets = relation.get_config().should_check_missing_streets()
        if streets == "only":
            continue

        info("update_ref_housenumbers: start: %s", relation_name)
        relation.write_ref_housenumbers(references)
        info("update_ref_housenumbers: end: %s", relation_name)


def update_ref_streets(relations: areas.Relations, update: bool) -> None:
    """Update the reference street list of all relations."""
    for relation_name in relations.get_active_names():
        relation = relations.get_relation(relation_name)
        if not update and os.path.exists(relation.get_files().get_ref_streets_path()):
            continue
        reference = config.Config.get_reference_street_path()
        streets = relation.get_config().should_check_missing_streets()
        if streets == "no":
            continue

        info("update_ref_streets: start: %s", relation_name)
        relation.write_ref_streets(reference)
        info("update_ref_streets: end: %s", relation_name)


def update_missing_housenumbers(relations: areas.Relations, update: bool) -> None:
    """Update the relation's house number coverage stats."""
    info("update_missing_housenumbers: start")
    for relation_name in relations.get_active_names():
        relation = relations.get_relation(relation_name)
        if not update and os.path.exists(relation.get_files().get_housenumbers_percent_path()):
            continue
        streets = relation.get_config().should_check_missing_streets()
        if streets == "only":
            continue

        relation.write_missing_housenumbers()
    info("update_missing_housenumbers: end")


def update_missing_streets(relations: areas.Relations, update: bool) -> None:
    """Update the relation's street coverage stats."""
    info("update_missing_streets: start")
    for relation_name in relations.get_active_names():
        relation = relations.get_relation(relation_name)
        if not update and os.path.exists(relation.get_files().get_streets_percent_path()):
            continue
        streets = relation.get_config().should_check_missing_streets()
        if streets == "no":
            continue

        relation.write_missing_streets()
    info("update_missing_streets: end")


def update_stats() -> None:
    """Performs the update of country-level stats."""

    # Fetch house numbers for the whole country.
    info("update_stats: start, updating whole-country csv")
    query = util.get_content(config.get_abspath("data/street-housenumbers-hungary.txt"))
    statedir = config.get_abspath("workdir/stats")
    os.makedirs(statedir, exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    csv_path = os.path.join(statedir, "%s.csv" % today)

    retry = 0
    while should_retry(retry):
        if retry > 0:
            info("update_stats: try #%s", retry)
        retry += 1
        try:
            overpass_sleep()
            response = overpass_query.overpass_query(query)
            with open(csv_path, "w") as stream:
                stream.write(response)
            break
        except urllib.error.HTTPError as http_error:
            info("update_stats: http error: %s", str(http_error))

    # Shell part.
    info("update_stats: executing the shell part")
    subprocess.run([config.get_abspath("stats-daily.sh")], check=True)

    # Remove old CSV files as they are created daily and each is around 11M.
    current_time = time.time()
    for csv in glob.glob(os.path.join(statedir, "*.csv")):
        creation_time = os.path.getmtime(csv)
        if (current_time - creation_time) // (24 * 3600) >= 7:
            os.unlink(csv)
            info("update_stats: removed old %s", csv)

    info("update_stats: generating json")
    json_path = os.path.join(statedir, "stats.json")
    with open(json_path, "w") as stream:
        stats.generate_json(statedir, stream)

    info("update_stats: end")


def our_main(relations: areas.Relations, mode: str, update: bool) -> None:
    """Performs the actual nightly task."""
    if mode in ("all", "stats"):
        update_stats()
    if mode in ("all", "relations"):
        update_osm_streets(relations, update)
        update_osm_housenumbers(relations, update)
        update_ref_streets(relations, update)
        update_ref_housenumbers(relations, update)
        update_missing_streets(relations, update)
        update_missing_housenumbers(relations, update)

    pid = str(os.getpid())
    with open("/proc/" + pid + "/status", "r") as stream:
        vm_peak = ""
        while True:
            line = stream.readline()
            if line.startswith("VmPeak:"):
                vm_peak = line.strip()
            if vm_peak or not line:
                info("our_main: %s", line.strip())
                break


def main() -> None:
    """Commandline interface to this module."""

    util.set_locale()

    workdir = config.Config.get_workdir()
    relations = areas.Relations(workdir)
    logpath = os.path.join(workdir, "cron.log")
    logging.basicConfig(filename=logpath,
                        level=logging.INFO,
                        format='%(message)s')
    handler = logging.StreamHandler()
    logging.getLogger().addHandler(handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("--refcounty", type=str,
                        help="limit the list of relations to a given refcounty")
    parser.add_argument("--refsettlement", type=str,
                        help="limit the list of relations to a given refsettlement")
    parser.add_argument('--no-update', dest='update', action='store_false',
                        help="don't update existing state of relations")
    parser.add_argument("--mode", choices=["all", "stats", "relations"],
                        help="only perform the given sub-task or all of them")
    parser.set_defaults(update=True, mode="relations")
    args = parser.parse_args()

    start = time.time()
    relations.activate_all(config.Config.get_cron_update_inactive())
    relations.limit_to_refcounty(args.refcounty)
    relations.limit_to_refsettlement(args.refsettlement)
    try:
        our_main(relations, args.mode, args.update)
    # pylint: disable=broad-except
    except Exception:
        error("main: unhandled exception: %s", traceback.format_exc())
    delta = time.time() - start
    info("main: finished in %s", str(datetime.timedelta(seconds=delta)))
    logging.getLogger().removeHandler(handler)
    logging.shutdown()


if __name__ == "__main__":
    main()

# vim:set shiftwidth=4 softtabstop=4 expandtab:
