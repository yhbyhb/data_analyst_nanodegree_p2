"""
Auditing and cleaning adresses

Referenced Lesson 6 - 11 Improving Street Names
"""
import xml.etree.cElementTree as ET
from collections import defaultdict
import re
import pprint
import codecs
import json

OSMFILE = "map.osm"
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)


expected = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", 
            "Trail", "Parkway", "Commons"]

# UPDATE THIS VARIABLE
mapping = { "St": "Street",
            "St.": "Street",
            "Rd" : "Road",
            "Rd.": "Road",
            "Ave" : "Avenue",
            "ave" : "Avenue"
            }


def audit_street_type(street_types, street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)


def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")


def audit(osmfile):
    osm_file = open(osmfile, "r")
    street_types = defaultdict(set)
    for event, elem in ET.iterparse(osm_file, events=("start",)):

        if elem.tag == "node" or elem.tag == "way":
            for tag in elem.iter("tag"):
                if is_street_name(tag):
                    audit_street_type(street_types, tag.attrib['v'])

    return street_types

# cleaning address by using this
def update_name(name, mapping):
    for key in mapping.keys():
        k = key.rstrip('.')
        n = name.rstrip('.')
        pattern = r'\b'+ k + r'\b'
        if re.search(pattern, n) != None:
            p = re.compile(pattern)
            name = re.sub(p, mapping[key], n)

    return name


def test():
    st_types = dict(audit(OSMFILE))

    # auditing
    with codecs.open('audit.log', "w") as fout:
        pprint.pprint(st_types, fout)

    # genereting expected cleaned results
    with codecs.open('clean.log', "w") as fout:
        pprint.pprint('name | better name', fout)
        pprint.pprint('------------- | ------------- ', fout)
        for st_type, ways in st_types.iteritems():
            for name in ways:
                better_name = update_name(name, mapping)
                if (name != better_name):
                    pprint.pprint(name + ' | ' + better_name, fout)

if __name__ == '__main__':
    test()
