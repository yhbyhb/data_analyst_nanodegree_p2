#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
import pprint
import re
import codecs
import json
import audit
"""
Wrangle the data and transform the shape of the data into the model used in Lesson 6 - 12 Preparing for Database
The output is a list of dictionaries
that look like this:

{
"id": "2406124091",
"type: "node",
"visible":"true",
"created": {
          "version":"2",
          "changeset":"17206049",
          "timestamp":"2013-08-03T16:43:42Z",
          "user":"linuxUser16",
          "uid":"1219059"
        },
"pos": [41.9757030, -87.6921867],
"address": {
          "housenumber": "5157",
          "postcode": "60625",
          "street": "North Lincoln Ave"
        },
"amenity": "restaurant",
"cuisine": "mexican",
"name": "La Cabana De Don Luis",
"phone": "1 (773)-271-5176"
}

Details are same as Lesson 6 - 12 Preparing for Database
"""

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = [ "version", "changeset", "timestamp", "user", "uid"]


def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way" :
        node["id"] = element.attrib["id"]
        if "visible" in element.attrib:
            node["visible"] = element.attrib["visible"]
        node["type"] = element.tag
        if "lat" in element.attrib:
            node["pos"] = [float(element.attrib["lat"]), float(element.attrib["lon"])]

        created = {}
        for key in CREATED:
          created[key] = element.attrib[key]
        node["created"] = created

        node_refs = []
        address = {}

        for child in element:
            if child.tag == "tag":
                k = child.attrib['k']
                if re.search(problemchars, k) != None:
                    continue
                elif re.search(lower, k) != None:
                    node[k] = child.attrib['v']
                elif re.search(lower_colon, k) != None:
                    if k.startswith("addr:") and len(k.split(":")) == 2:
                        name = child.attrib['v'];
                        better_name = audit.update_name(name, audit.mapping)
                        address[k.split(":")[1]] = better_name
            elif child.tag == "nd":
                node_refs.append(child.attrib["ref"])

        if len(node_refs) > 0:
            node["node_refs"] = node_refs
        if len(address) > 0:
            node["address"] = address

        return node
    else:
        return None


def process_map(file_in, pretty = False):
    file_out = "{0}.json".format(file_in)
    data = []
    # iterative parsing and writing JSON file
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data

def test():
    # wrangling osm file and save to JSON file
    map_file_name = 'map.osm'
    data = process_map(map_file_name, False)

    # inserting to mongoDB
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017")
    db = client.p2
    db.osm.insert(data)

if __name__ == "__main__":
    test()