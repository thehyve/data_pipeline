import opentargets.model.core as opentargets
import opentargets.model.bioentity as bioentity
import opentargets.model.evidence.phenotype as evidence_phenotype
import opentargets.model.evidence.core as evidence_core
import opentargets.model.evidence.linkout as evidence_linkout
import opentargets.model.evidence.association_score as association_score
import opentargets.model.evidence.mutation as evidence_mutation
import json
import sys
import gzip
import logging
import urllib2
import csv
from mrtarget.Settings import Config

'''
Extracted input JSONs from Postgres with the following command
psql -h localhost -d cttv_core_test -p 5432 -U tvdev -A -F $'\t' -X -t -c "SELECT JSON_BUILD_OBJECT('disease', disease, 'target', target, 'disease_label', disease_label, 'gene_symbol', gene_symbol) FROM gene2phenotype.final_data_for_evstrs_jul2016" >final_data_for_evstrs_jul2016.json
This is a skeleton only, need to add fields for score and evidence codes.
'''

class G2P():

    def __init__(self):
        self.omim_to_efo_map = dict()
        self.evidence_strings = list()
        self._logger = logging.getLogger(__name__)


    def get_omim_to_efo_mappings(self):
        self._logger.info("OMIM to EFO parsing - requesting from URL %s" % Config.OMIM_TO_EFO_MAP_URL)
        req = urllib2.Request(Config.OMIM_TO_EFO_MAP_URL)
        response = urllib2.urlopen(req)
        self._logger.info("OMIM to EFO parsing - response code %s" % response.code)
        lines = response.readlines()
        for line in lines:
            '''
            omim	efo_uri	efo_label	source	status

            '''
            (omim, efo_uri, efo_label, source, status) = line.split("\t")
            if omim not in self.omim_to_efo_map:
                self.omim_to_efo_map[omim] = []
            self.omim_to_efo_map[omim].append({'efo_uri': efo_uri, 'efo_label': efo_label})

    def generate_evidence_strings(self, source_file):

        total_efo = 0
        self.get_omim_to_efo_mappings()

        with gzip.open(source_file, mode='r') as zf:
            reader = csv.reader(zf, delimiter=',', quotechar='"')
            c = 0
            for row in reader:
                c += 1
                if c > 1:

                    '''
                    "gene symbol","gene mim","disease name","disease mim","DDD category","allelic requirement","mutation consequence",phenotypes,"organ specificity list",pmids,panel,"prev symbols","hgnc id"
                    '''
                    (gene_symbol, gene_mim, disease_name, disease_mim, DDD_category, allelic_requirement, mutation_consequence, phenotypes, organ_specificity_list,pmids,panel, prev_symbols, hgnc_id) = row
                    ''' map gene to ensembl '''
                    target = "ENSG00000215612"

                    ''' Map disease to EFO or Orphanet '''
                    if disease_mim in self.omim_to_efo_map:
                        total_efo +=1
                        disease = self.omim_to_efo_map[disease_mim]

                        obj = opentargets.Literature_Curated(type='genetic_literature')
                        provenance_type = evidence_core.BaseProvenance_Type(
                            database=evidence_core.BaseDatabase(
                                id="Gene2Phenotype",
                                version='v0.2',
                                dbxref=evidence_core.BaseDbxref(
                                    url="http://www.ebi.ac.uk/gene2phenotype",
                                    id="Gene2Phenotype", version="v0.2")),
                            literature=evidence_core.BaseLiterature(
                                references=[evidence_core.Single_Lit_Reference(lit_id="http://europepmc.org/abstract/MED/25529582")]
                            )
                        )
                        obj.access_level = "public"
                        obj.sourceID = "gene2phenotype"
                        obj.validated_against_schema_version = "1.2.5"
                        obj.unique_association_fields = {"target": target, "disease_uri": disease['efo_uri'], "source_id": "gene2phenotype"}
                        obj.target = bioentity.Target(id=target,
                                                      activity="http://identifiers.org/cttv.activity/unknown",
                                                      target_type='http://identifiers.org/cttv.target/gene_evidence',
                                                      target_name=gene_symbol)
                        # http://www.ontobee.org/ontology/ECO?iri=http://purl.obolibrary.org/obo/ECO_0000204 -- An evidence type that is based on an assertion by the author of a paper, which is read by a curator.
                        resource_score = association_score.Probability(
                            type="probability",
                            method=association_score.Method(
                                description="NA",
                                reference="NA",
                                url="NA"),
                            value=1)

                        obj.disease = bioentity.Disease(id=disease['efo_uri'], name=disease['efo_label'], source_name=disease_name)
                        obj.evidence = evidence_core.Literature_Curated()
                        obj.evidence.is_associated = True
                        obj.evidence.evidence_codes = ["http://purl.obolibrary.org/obo/ECO_0000204"]
                        obj.evidence.provenance_type = provenance_type
                        obj.evidence.date_asserted = '2017-06-13'
                        obj.evidence.provenance_type = provenance_type
                        obj.evidence.resource_score = resource_score
                        linkout = evidence_linkout.Linkout(
                            url='http://www.ebi.ac.uk/gene2phenotype/gene2phenotype-webcode/cgi-bin/handler.cgi?panel=ALL&search_term=%s' % (
                            symbol,),
                            nice_name='Gene2Phenotype%s' % (symbol))
                        obj.evidence.urls = [linkout]
                        error = obj.validate(logging)
                        if error > 0:
                            logging.error(obj.to_JSON())
                            sys.exit(1)
                        else:
                            self.evidence_strings.append(obj)

            print "%i %i" % (total_efo, c)

    def write_evidence_strings(self, filename):
        logging.info("Writing IntOGen evidence strings")
        with open(filename, 'w') as tp_file:
            n = 0
            for evidence_string in self.evidence_strings:
                n += 1
                logging.info(evidence_string.disease.id[0])
                # get max_phase_for_all_diseases
                error = evidence_string.validate(logging)
                if error == 0:
                    tp_file.write(evidence_string.to_JSON(indentation=None) + "\n")
                else:
                    logging.error("REPORTING ERROR %i" % n)
                    logging.error(evidence_string.to_JSON(indentation=4))
                    # sys.exit(1)
        tp_file.close()

def main():


    g2p = G2P()
    source_file = "/Users/otvisitor/Downloads/DDG2P_13_5_2017.csv.gz"
    g2p.generate_evidence_strings(source_file)

    #source_file = sys.argv[1]
    #g2p = G2P()
    #g2p.read_file(source_file)
    #g2p.write_evidence_strings('/Users/koscieln/Documents/data/ftp/cttv001/upload/submissions/cttv001_gene2phenotype-29-07-2016.json')

if __name__ == "__main__":
    main()