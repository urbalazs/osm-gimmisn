#!/usr/bin/env python3
#
# Copyright 2020 Miklos Vajna. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

"""The wsgi module contains functionality specific to the json part of the web interface."""

import json
import urllib.parse
from typing import Dict
from typing import Iterable
from typing import List
from typing import TYPE_CHECKING
from typing import Tuple

import areas
import config
import overpass_query
import webframe

if TYPE_CHECKING:
    # pylint: disable=no-name-in-module,import-error,unused-import
    from wsgiref.types import StartResponse


def streets_update_result_json(relations: areas.Relations, request_uri: str) -> str:
    """Expected request_uri: e.g. /osm/streets/ormezo/update-result.json."""
    tokens = request_uri.split("/")
    relation_name = tokens[-2]
    relation = relations.get_relation(relation_name)
    query = relation.get_osm_streets_query()
    ret: Dict[str, str] = {}
    try:
        relation.get_files().write_osm_streets(overpass_query.overpass_query(query))
        ret["error"] = ""
    except urllib.error.HTTPError as http_error:
        ret["error"] = str(http_error)
    return json.dumps(ret)


def street_housenumbers_update_result_json(relations: areas.Relations, request_uri: str) -> str:
    """Expected request_uri: e.g. /osm/street-housenumbers/ormezo/update-result.json."""
    tokens = request_uri.split("/")
    relation_name = tokens[-2]
    relation = relations.get_relation(relation_name)
    query = relation.get_osm_housenumbers_query()
    ret: Dict[str, str] = {}
    try:
        relation.get_files().write_osm_housenumbers(overpass_query.overpass_query(query))
        ret["error"] = ""
    except urllib.error.HTTPError as http_error:
        ret["error"] = str(http_error)
    return json.dumps(ret)


def our_application_json(
        start_response: 'StartResponse',
        relations: areas.Relations,
        request_uri: str
) -> Iterable[bytes]:
    """Dispatches json requests based on their URIs."""
    content_type = "application/json"
    extra_headers: List[Tuple[str, str]] = []
    prefix = config.Config.get_uri_prefix()
    if request_uri.startswith(prefix + "/streets/"):
        output = streets_update_result_json(relations, request_uri)
    else:
        # Assume that request_uri starts with prefix + "/street-housenumbers/".
        output = street_housenumbers_update_result_json(relations, request_uri)
    return webframe.send_response(start_response, content_type, "200 OK", output, extra_headers)

# vim:set shiftwidth=4 softtabstop=4 expandtab: