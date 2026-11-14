#!/usr/bin/env python
# This file is part of ts_planning_tool.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Read a "Test Cycle Publication notes" page from Confluence as text.

Uses the same Atlassian credentials as zapi (JIRA_USERNAME, JIRA_API_TOKEN).
This script only reads; link_cycles.py uses `request` to save a page.
Standard library only.

    python confluence_page.py --list          # latest notes pages
    python confluence_page.py 2259222570      # one page, by id or URL

The output keeps what matters for drafting: headings, list nesting,
links, ~~strikethrough~~, [status: READY], [jira: SVAB-20], [date: ...].
"""

import argparse
import base64
import gzip
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

SITE = "https://rubinobs.atlassian.net"
# "Test Cycle Publication Notes" in the LSSTOps space; the weekly pages are
# its children.
NOTES_PARENT_ID = "2101608457"


def request(path, method="GET", payload=None):
    """Call a Confluence REST path and return the decoded JSON."""
    username = os.environ.get("JIRA_USERNAME", "")
    if "@" not in username:
        username = f"{username}@lsst.org"
    token = os.environ["JIRA_API_TOKEN"]
    auth = base64.b64encode(f"{username}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{SITE}/wiki/rest/api/{path}", data=data, method=method, headers=headers
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return json.loads(body)


class StorageToText(HTMLParser):
    """Convert Confluence storage format (XHTML + ac: macros) to text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.depth = 0
        self.links = []
        self.macros = []  # stack of [name, params]
        self.param = None  # name of the ac:parameter being read
        self.skip = 0  # inside elements whose text is noise

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "div", "br", "tr"):
            self.out.append("\n" + "  " * self.depth)
        elif tag in ("ul", "ol"):
            self.depth += 1
        elif tag in ("li", "ac:task"):
            self.out.append("\n" + "  " * max(self.depth - 1, 0) + "- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in ("s", "del", "strike"):
            self.out.append("~~")
        elif tag == "span" and "line-through" in (a.get("style") or ""):
            self.out.append("~~")
            self.links.append("__strike__")
        elif tag == "a":
            self.links.append(a.get("href"))
        elif tag == "ri:page":
            self.out.append(f"[page: {a.get('ri:content-title')}]")
        elif tag == "time":
            self.out.append(f"[date: {a.get('datetime')}]")
        elif tag == "ac:structured-macro":
            self.macros.append([a.get("ac:name"), {}])
        elif tag == "ac:parameter":
            self.param = a.get("ac:name")
        elif tag in ("ac:task-id", "ac:task-uuid", "ac:task-status"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("ul", "ol"):
            self.depth -= 1
        elif tag in ("s", "del", "strike"):
            self.out.append("~~")
        elif tag == "span" and self.links and self.links[-1] == "__strike__":
            self.links.pop()
            self.out.append("~~")
        elif tag == "a":
            href = self.links.pop() if self.links else None
            if href and href != "__strike__":
                self.out.append(f" <{href}>")
        elif tag == "ac:parameter":
            self.param = None
        elif tag == "ac:structured-macro" and self.macros:
            name, params = self.macros.pop()
            if name == "status":
                self.out.append(f"[status: {params.get('title', '').strip()}] ")
            elif name == "jira" and params.get("key"):
                self.out.append(f"[jira: {params['key'].strip()}] ")
        elif tag in ("ac:task-id", "ac:task-uuid", "ac:task-status"):
            self.skip -= 1

    def handle_data(self, data):
        if self.skip:
            return
        if self.param is not None and self.macros:
            params = self.macros[-1][1]
            params[self.param] = params.get(self.param, "") + data
            return
        self.out.append(data)

    def text(self):
        text = "".join(self.out)
        text = re.sub(r"~~(\s*)~~", r"\1", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def page_id(value):
    """Accept a page id or any Confluence URL that contains /pages/<id>."""
    match = re.search(r"/pages/([0-9]+)", value)
    return match.group(1) if match else value


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("page", nargs="?", help="Page id or URL")
    parser.add_argument(
        "--list", action="store_true", help="List the latest notes pages"
    )
    args = parser.parse_args()

    if args.list or not args.page:
        children = request(
            f"content/{NOTES_PARENT_ID}/child/page?limit=200&expand=version"
        )["results"]
        for child in children[-10:]:
            print(
                f"{child['id']}  {child['title']}  "
                f"(v{child['version']['number']}, {child['version']['when'][:10]})"
            )
        return

    page = request(f"content/{page_id(args.page)}?expand=body.storage,version")
    converter = StorageToText()
    converter.feed(page["body"]["storage"]["value"])
    url = SITE + "/wiki" + page["_links"]["webui"]
    print(f"# {page['title']}")
    print(f"page_id: {page['id']}  version: {page['version']['number']}  url: {url}\n")
    print(converter.text())


if __name__ == "__main__":
    sys.exit(main())
