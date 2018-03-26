import subprocess
import os
import jsonasobj
import pandas as pd
import requests
from SPARQLWrapper import SPARQLWrapper, JSON
from ShExJSG import ShExC
import json
import pprint
import sys

from pyshex import PrefixLibrary, ShExEvaluator
from sparql_slurper import SlurpyGraph

def get_sparql_dataframe(service, query):
    """
    Helper function to convert SPARQL results into a Pandas data frame.
    """
    sparql = SPARQLWrapper(service)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    result = sparql.query()

    processed_results = jsonasobj.load(result.response)
    cols = processed_results.head.vars

    out = []
    for row in processed_results.results.bindings:
        item = []
        for c in cols:
            item.append(row._as_dict.get(c, {}).get('value'))
        out.append(item)

    return pd.DataFrame(out, columns=cols)

def run_shex_manifest():
    #manifest = \
    #    "https://raw.githubusercontent.com/SuLab/Genewiki-ShEx/master/pathways/wikipathways/manifest_all.json"
    manifest = jsonasobj.loads(requests.get(os.environ['MANIFEST_URL']).text)
    print(os.environ['MANIFEST_URL'])
    for case in manifest:
        print(case._as_json_dumps())
        if case.data.startswith("Endpoint:"):
            sparql_endpoint = case.data.replace("Endpoint: ", "")
            schema = requests.get(case.schemaURL).text
            shex = ShExC(schema).schema
            print("==== Schema =====")
            #print(shex._as_json_dumps())

            evaluator = ShExEvaluator(schema=shex, debug=True)
            sparql_query = case.queryMap.replace("SPARQL '''", "").replace("'''@START", "")

            df = get_sparql_dataframe(sparql_endpoint, sparql_query)
            for wdid in df.item:
                slurpeddata = SlurpyGraph(sparql_endpoint)
                # slurpeddata = requests.get(wdid + ".ttl")

                results = evaluator.evaluate(rdf=slurpeddata, focus=wdid, debug=True)
                for result in results:
                    if result.result:
                        print(str(result.focus) + ": CONFORMS")
                    else:
                        if str(result.focus) in [
                            "http://www.wikidata.org/entity/Q33525",
                            "http://www.wikidata.org/entity/Q62736",
                            "http://www.wikidata.org/entity/Q112670"
                        ]:
                            continue
                        print(
                            "item with issue: " + str(result.focus) + " - " + "shape applied: " + str(result.start))
                        shapemap = "[{\"node\": \"" + str(result.focus) + "\", \"shape\":\"http://micel.io/genewiki/disease\"}]"
                        cmd = ["/tmp/shex.js/bin/validate", "-x", "https://raw.githubusercontent.com/SuLab/Genewiki-ShEx/master/diseases/wikidata-disease-ontology.shex", "--endpoint", "https://query.wikidata.org/bigdata/namespace/wdq/sparql", "--map", shapemap]
                        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
                        #result = subprocess.run(cmd, stdout=subprocess.PIPE)
                        ShExErrors = json.loads(result.stdout.decode('utf-8'))
                        # pprint.pprint(ShExErrors)
                        for error in ShExErrors["errors"]:
                            print(error["constraint"]["type"]+": "+error["constraint"]["predicate"])
                        sys.exit()
                        #print(cmd)



run_shex_manifest()