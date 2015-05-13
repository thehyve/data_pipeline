import logging
from elasticsearch import Elasticsearch
from common import Actions
from common.ElasticsearchLoader import Loader
from common.PGAdapter import Adapter
from modules.ECO import EcoActions, EcoProcess, EcoUploader
from modules.EFO import EfoActions, EfoProcess, EfoUploader
from modules.EvidenceString import EvidenceStringActions, EvidenceStringProcess, EvidenceStringUploader
from modules.GeneData import GeneActions, GeneManager, GeneUploader
from modules.HPA import HPADataDownloader, HPAActions, HPAProcess, HPAUploader
from modules.Uniprot import UniProtActions,UniprotDownloader
import argparse
from settings import Config, ElasticSearchConfiguration


__author__ = 'andreap'
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='CTTV processing pipeline')
    parser.add_argument("--all", dest='all', help="run the full pipeline (at your own risk)",
                        action="append_const", const = Actions.ALL)
    parser.add_argument("--hpad", dest='hpa', help="download data from human protein atlas and store it in postgres",
                        action="append_const", const = HPAActions.DOWNLOAD)
    parser.add_argument("--hpap", dest='hpa', help="process human protein atlas data stored in postgres and create json object",
                        action="append_const", const = HPAActions.PROCESS)
    parser.add_argument("--hpau", dest='hpa', help="upload processed human protein atlas json obects stored in postgres to elasticsearch",
                        action="append_const", const = HPAActions.UPLOAD)
    parser.add_argument("--hpa", dest='hpa', help="download human protein atlas data, process it and upload it to elasticsearch",
                        action="append_const", const = HPAActions.ALL)
    parser.add_argument("--unic", dest='uni', help="cache the live version of uniprot human entries in postgresql",
                        action="append_const", const = UniProtActions.CACHE)
    parser.add_argument("--genm", dest='gen', help="merge the available gene information and store the resulting json objects in postgres",
                        action="append_const", const = GeneActions.MERGE)
    parser.add_argument("--genu", dest='gen', help="upload the stored json gene object to elasticsearch",
                        action="append_const", const = GeneActions.UPLOAD)
    parser.add_argument("--gena", dest='gen', help="merge the available gene information, store the resulting json objects in postgres and upload them in elasticsearch",
                        action="append_const", const = GeneActions.ALL)
    parser.add_argument("--efop", dest='efo', help="process the efo information and store the resulting json objects in postgres",
                        action="append_const", const = EfoActions.PROCESS)
    parser.add_argument("--efou", dest='efo', help="upload the stored json efo object to elasticsearch",
                        action="append_const", const = EfoActions.UPLOAD)
    parser.add_argument("--efoa", dest='efo', help="process the efo information, store the resulting json objects in postgres and upload them in elasticsearch",
                        action="append_const", const = EfoActions.ALL)
    parser.add_argument("--ecop", dest='eco', help="process the eco information and store the resulting json objects in postgres",
                        action="append_const", const = EcoActions.PROCESS)
    parser.add_argument("--ecou", dest='eco', help="upload the stored json efo object to elasticsearch",
                        action="append_const", const = EcoActions.UPLOAD)
    parser.add_argument("--ecoa", dest='eco', help="process the eco information, store the resulting json objects in postgres and upload them in elasticsearch",
                        action="append_const", const = EcoActions.ALL)
    parser.add_argument("--evsp", dest='evs', help="process and validate the available evidence strings and store the resulting json object in postgres ",
                        action="append_const", const = EvidenceStringActions.PROCESS)
    parser.add_argument("--evsu", dest='evs', help="upload the stored json evidence string object to elasticsearch",
                        action="append_const", const = EvidenceStringActions.UPLOAD)
    parser.add_argument("--evsa", dest='evs', help="process and validate the available evidence strings, store the resulting json objects in postgres and upload them in elasticsearch",
                        action="append_const", const = EvidenceStringActions.ALL)
    args = parser.parse_args()

    adapter = Adapter()
    '''init es client'''
    print 'pointing to elasticsearch at:', Config.ELASTICSEARCH_URL
    es = Elasticsearch(Config.ELASTICSEARCH_URL)
    # es = Elasticsearch(["10.0.0.11:9200"],
    # # sniff before doing anything
    #                     sniff_on_start=True,
    #                     # refresh nodes after a node fails to respond
    #                     sniff_on_connection_fail=True,
    #                     # and also every 60 seconds
    #                     sniffer_timeout=60)
    #
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('elasticsearch').setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    with Loader(es, chunk_size=ElasticSearchConfiguration.bulk_load_chunk) as loader:
        run_full_pipeline = False
        if args.all  and (Actions.ALL in args.all):
            run_full_pipeline = True
        if args.hpa or run_full_pipeline:
            do_all = (HPAActions.ALL in args.hpa) or run_full_pipeline
            if (HPAActions.DOWNLOAD in args.hpa) or do_all:
                HPADataDownloader(adapter).retrieve_all()
            if (HPAActions.PROCESS in args.hpa) or do_all:
                HPAProcess(adapter).process_all()
            if (HPAActions.UPLOAD in args.hpa) or do_all:
                HPAUploader(adapter, loader).upload_all()
        if args.uni or run_full_pipeline:
            do_all = (UniProtActions.ALL in args.uni) or run_full_pipeline
            if (UniProtActions.CACHE in args.uni) or do_all:
                UniprotDownloader(adapter).cache_human_entries()
        if args.gen or run_full_pipeline:
            do_all = (GeneActions.ALL in args.gen) or run_full_pipeline
            if (GeneActions.MERGE in args.gen) or do_all:
                GeneManager(adapter).merge_all()
            if (GeneActions.UPLOAD in args.gen) or do_all:
                GeneUploader(adapter, loader).upload_all()
        if args.efo or run_full_pipeline:
            do_all = (EfoActions.ALL in args.efo) or run_full_pipeline
            if (EfoActions.PROCESS in args.efo) or do_all:
                EfoProcess(adapter).process_all()
            if (EfoActions.UPLOAD in args.efo) or do_all:
                EfoUploader(adapter, loader).upload_all()
        if args.eco or run_full_pipeline:
            do_all = (EcoActions.ALL in args.eco) or run_full_pipeline
            if (EcoActions.PROCESS in args.eco) or do_all:
                EcoProcess(adapter).process_all()
            if (EcoActions.UPLOAD in args.eco) or do_all:
                EcoUploader(adapter, loader).upload_all()
        if args.evs or run_full_pipeline:
            do_all = (EvidenceStringActions.ALL in args.evs) or run_full_pipeline
            if (EvidenceStringActions.PROCESS in args.evs) or do_all:
                EvidenceStringProcess(adapter).process_all()
            if (EvidenceStringActions.UPLOAD in args.evs) or do_all:
                EvidenceStringUploader(adapter, loader).upload_all()

