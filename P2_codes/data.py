#!/usr/bin/env python
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
import pprint
import re
import codecs
from bson import json_util
import json
import dateutil.parser
import audit
"""
data.py wrangles the data(.osm) and transform the shape of the data into the model that 
is similar with used in Lesson 6 - 12 Preparing for Database.
function 'process_map' and 'insert_map_data' are executed sequentially.

the function 'process_map' iteratively parses map data(map.osm) and writes to JSON file.
It returns a list of dictionaries for inserting DB.
It iteratively parses xml element by calling the function 'shape_element'

the function 'shape_element' returns a dictionay, containing the shaped data for given element.
It audits and shaped a given element as follows.
- It shapes three basic data structures (top level tags), 'node', 'way' and 'relation'.
- It classified three top level tags with key 'type', for instance
  {...
  "type": "node",
  ...
  }

- all attributes of "node", "way" and "relation" turned into regular key/value pairs, except:
    - attributes in the CREATED array are added in dictionary under a key "created"
    - attributes for latitude and longitude are added to a "pos" array with floats values (converted from strings).
    - attributes for timestamp is parsed with datetime object using date aggregation operators. 
- if second level tag "k" value contains problematic characters, ignored.
- if second level tag "k" value contains upper case characters, ignored.
- if second level tag "k" value starts with "addr:", it is added to a dictionary "address"
- if second level tag "k" value does not start with "addr:", but contains ":", the function process it
  same as any other tag.
- if there is a second ":" that separates the type/direction of a street,
  the tag is ignored, for example:

    <tag k="addr:housenumber" v="5158"/>
    <tag k="addr:street" v="North Lincoln Avenue"/>
    <tag k="addr:street:name" v="Lincoln"/>
    <tag k="addr:street:prefix" v="North"/>
    <tag k="addr:street:type" v="Avenue"/>
    <tag k="amenity" v="pharmacy"/>

  are turned into:

    {...
    "address": {
        "housenumber": 5158,
        "street": "North Lincoln Avenue"
    }
    "amenity": "pharmacy",
    ...
    }

- The top level tag "way" has child elements named 'nd'. For instence,

  <nd ref="305896090"/>
  <nd ref="1719825889"/>

  are turned into

  "node_refs": ["305896090", "1719825889"]

- The top level tag 'relation' has child elemnts named 'member'. Attributes of 'member' are added in dictionary. 
  'member' dictionaies are added a list named 'members'. For instance,

    <member ref="333202546" role="from" type="way" />
    <member ref="65449648" role="via" type="node" />
    <member ref="61237966" role="to" type="way" />
  
  are turned into:

  "members": [
    {
      "role": "from", 
      "ref": "333202546", 
      "type": "way"
    }, 
    {
      "role": "via", 
      "ref": "65449648", 
      "type": "node"
    }, 
    {
      "role": "to", 
      "ref": "61237966", 
      "type": "way"
    }
  ]

- Also, 'relation' has a second level tag 'type'. It confilcts with key 'type' as mentioned above.
  So type of relation is converted as follow,

    <tag k="type" v="route" />

  are turned into:

    "relation_type": "route"

the function 'insert_map_data' insert a list of dictionaries from function 'process_map' to mongoDB.

"""

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = [ "version", "changeset", "user", "uid"]

def shape_element(element):
    node = {}
    # Allows only three basic top level elements
    if element.tag in ('node', 'way', 'relation'):
        # Adding type
        node["type"] = element.tag

        # Adding attribues - generals
        node["id"] = element.attrib["id"]
        if "visible" in element.attrib:
            node["visible"] = element.attrib["visible"]

        # Adding attribues - exceptions #1 'created'
        created = {}
        for key in CREATED:
          created[key] = element.attrib[key]
        # convert from date string to datetime object
        created['timestamp'] = dateutil.parser.parse(element.attrib['timestamp'])
        node["created"] = created

        # Adding attribues - exceptions #2 shaping position
        if "lat" in element.attrib and "lon" in element.attrib:
            node["pos"] = [float(element.attrib["lat"]), float(element.attrib["lon"])]

        # Adding child elements
        node_refs = []
        address = {}
        members = []
        for child in element:
            # Auditing and shaping "tag" elements
            if child.tag == "tag":
                k = child.attrib['k']
                # Ignoring key including problematic characters
                if re.search(problemchars, k) != None:
                    continue
                # Ignoring key including upper case characters
                if re.search(lower, k) != None:
                    # Handling confilcts when second level tag "k" value is 'type'
                    if k == 'type':
                        node[element.tag + '_type'] = child.attrib['v']
                    else:
                        node[k] = child.attrib['v']
                # Ignoring key including problematic characters
                if re.search(lower_colon, k) != None:
                    if k.startswith("addr:"):
                        if len(k.split(":")) == 2 :
                            v = child.attrib['v']
                            # cleaning street 
                            if k == "addr:street":
                                v = audit.update_name(v, audit.mapping)
                            address[k.split(":")[1]] = v
                    else:
                        node[k] = child.attrib['v']
            # for 'way'
            elif child.tag == "nd":
                node_refs.append(child.attrib["ref"])
            # for 'relation'
            elif child.tag == 'member':
                member = {}
                member['ref'] = child.attrib['ref']
                member['role'] = child.attrib['role']
                member['type'] = child.attrib['type']
                members.append(member)

        if len(node_refs) > 0:
            node["node_refs"] = node_refs
        if len(address) > 0:
            node["address"] = address
        if len(members) > 0:
            node["members"] = members

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
                # Using json_util.default parser for datetime object
                if pretty:
                    fo.write(json.dumps(el, indent=2, default=json_util.default )+"\n")
                else:
                    fo.write(json.dumps(el, default=json_util.default) + "\n")
    return data

def insert_map_data(data):
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017")
    db = client.p2
    db.osm.insert(data)

def test():
    # wrangling osm file and save to JSON file
    map_file_name = 'map.osm'
    data = process_map(map_file_name, False)

    # inserting to mongoDB
    insert_map_data(data)

if __name__ == "__main__":
    test()
