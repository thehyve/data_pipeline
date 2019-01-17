import os

import configargparse
from Settings import Config


"""
This will create a singleton argument parser that is appropriately configured
with the various command line, environment, and ini/yaml file options.

Note that backwards compatibility of arguments is not guaranteed. To ensure
legacy arguments are interpreted, use get_args()
"""

def setup_parser():
    p = configargparse.get_argument_parser(config_file_parser_class=configargparse.YAMLConfigFileParser)
    p.description = 'Open Targets processing pipeline'

    # argument to read config file
    p.add('-c', '--config', is_config_file=True,
        env_var="CONFIG", help='path to config file (YAML)')

    # logging
    p.add("--log-level", help="set the log level",
        env_var="LOG_LEVEL", action='store', default='INFO')
    p.add("--log-config", help="logging configuration file",
        env_var="LOG_CONFIG", action='store', default='mrtarget/resources/logging.ini')
    #TODO remove this as it can be captured inside a custom log config instead
    p.add("--log-http", help="log HTTP(S) requests in this file",
        env_var="LOG_HTTP", action='store')

    # take the release tag from the command line, but fall back to environment or ini files
    p.add('release_tag', nargs='?')

    # handle stage-specific QC
    p.add("--qc-out", help="TSV file to write/update qc information")
    p.add("--qc-in", help="TSV file to read qc information for comparison")
    p.add("--qc-only", help="only run the qc and not the stage itself",
        action="store_true")
    p.add("--skip-qc", help="do not run the qc for this stage",
        action="store_true")

    # load supplemental and genetic informtaion from various external resources
    p.add("--hpa", help="download human protein atlas, process, and store in elasticsearch",
        action="store_true")
    p.add("--ens", help="retrieve the latest ensembl gene records, store in elasticsearch",
        action="store_true")
    p.add("--unic", help="cache the uniprot human entries in elasticsearch",
        action="store_true")

    p.add("--rea", help="download reactome data, process it, and store elasticsearch",
        action="store_true")

    # use the sources to combine the gene information into a single new index
    p.add("--gen", help="merge the available gene information, store in elasticsearch",
        action="store_true")
    p.add("--gene-data-plugin-places", help="file paths to search for plugins",
        env_var="GENE_DATA_PLUGIN_PLACES", action="append")
    p.add("--gene-data-plugin-names", help="plugin names in order of invocation",
        env_var="GENE_DATA_PLUGIN_ORDER", action="append")
    

    # load various ontologies into various indexes
    p.add("--mp", help="process Mammalian Phenotype (MP), store the resulting json objects in elasticsearch",
        action="store_true")
    p.add("--efo", help="process Experimental Factor Ontology (EFO), store in elasticsearch",
        action="store_true")
    p.add("--eco", help="process Evidence and Conclusion Ontology (ECO), store in elasticsearch",
        action="store_true")

    # this generates a elasticsearch index from a source json file
    p.add("--val", help="check json file, validate, and store in elasticsearch",
        action="store_true")
    p.add("--input-file", help="pass the path to a gzipped file to use as input for the data validation step",
        action='append')
    p.add("--schema-version", help="set the schema version aka 'branch' name. Default is 'master'",
        env_var="SCHEMA_VERSION", default='master')
    p.add("--val-first-n", help="read only the first n lines from each input file",
        env_var="VAL_FIRST_N")

    # this is related to generating a combine evidence index from all the inidividual datasource indicies
    p.add("--evs", help="process and validate the available evidence strings, store in elasticsearch",
        action="store_true")
    p.add("--datasource", help="just process data for this datasource. Does not work with all the steps!!",
        action='append')

    # this has to be stored as "assoc" instead of "as" because "as" is a reserved name when accessing it later e.g. `args.as`
    p.add("--as", help="compute association scores, store in elasticsearch",
        action="store_true", dest="assoc")
    p.add("--targets", help="just process data for this target. Does not work with all the steps!!",
        action='append')

    # these are related to generated in a search index
    p.add("--sea", help="compute search results, store in elasticsearch",
        action="store_true")
    p.add("--skip-diseases", help="Skip adding diseases to the search index",
        action='store_true', default=False)
    p.add("--skip-targets", help="Skip adding targets to the search index",
        action='store_true', default=False)

    # additional information to add
    p.add("--ddr", help="compute data driven t2t and d2d relations, store in elasticsearch",
        action="store_true")

    # generate some high-level summary metrics over the release
    #TODO cleanup and possibly delete eventually
    p.add("--metric", help="generate metrics", action="store_true")
    p.add("--metric-file", help="generate metrics", 
        env_var="METRIC_FILE", default='release_metrics.txt')

    # quality control steps
    #TODO cleanup and possibly delete eventually
    p.add("--qc", help="Run quality control scripts",
        action="store_true")

    # use an external redis rather than spawning one ourselves
    p.add("--redis-remote", help="connect to a remote redis, instead of starting an embedded one",
        action='store_true', default=False,
        env_var='CTTV_REDIS_REMOTE')  # TODO use a different env variable
    p.add("--redis-host", help="redis host",
        action='store', default='localhost',
        env_var='REDIS_HOST')
    p.add("--redis-port", help="redis port",
        action='store', default='35000',
        env_var='REDIS_PORT')

    # elasticsearch
    p.add("--elasticseach-nodes", help="elasticsearch host(s)",
        action='append', default=['localhost:9200'],
        env_var='ELASTICSEARCH_NODES')
    p.add("--elasticsearch-folder", help="write to files instead of a live elasticsearch server",
        action='store') #this only applies to --val at the moment

    # for debugging
    p.add("--dump", help="dump core data to local gzipped files",
        action="store_true")
    p.add("--dry-run", help="do not store data in the backend, useful for dev work. Does not work with all the steps!!",
        action='store_true', default=False)
    p.add("--profile", help="magically profiling process() per process",
        action='store_true', default=False)

    # process handling
    #note this is the number of workers for each parallel operation
    #if there are multiple parallel operations happening at once, then 
    #this could be many more than that
    p.add("--num-workers", help="num worker processess for a parallel operation",
        env_var="NUM_WORKERS", action='store', default=4, type=int)
    p.add("--max-queued-events", help="max number of events to put per queue",
        env_var="MAX_QUEUED_EVENTS", action='store', default=10000, type=int)


    #reactome
    p.add("--reactome-pathway-data", help="location of reactome pathway file",
        env_var="REACTOME_PATHWAY_DATA", action='store')
    p.add("--reactome-pathway-relation", help="location of reactome pathway relationships file",
        env_var="REACTOME_PATHWAY_RELACTION", action='store')

    #gene plugins are configured in each plugin
    #helps separate the plugins from the rest of the pipeline
    #and makes it easier to manage custom plugins

    #uniprot
    # to generate this file you have to call
    # https://www.uniprot.org/uniprot/?query=reviewed%3Ayes%2BAND%2Borganism%3A9606&compress=yes&format=xml
    p.add("--uniprot_uri", help="location of uniprot file",
        env_var="UNIPROT_URI", action='store')

    #ensembl
    # It should be generated using the create_genes_dictionary.py script in opentargets/genetics_backend/makeLUTs
    #   python create_genes_dictionary.py -o "./" -e -z -n homo_sapiens_core_93_38
    p.add("--ensembl-filename", help="location of ensembl file",
        env_var="ENSEMBL_FILENAME", action='store')

    #hpa tissue specificity
    p.add("--tissue-translation-map", help="location of tissue translation map file",
        env_var="TISSUE_TRANSLATION_MAP", action='store')
    p.add("--tissue-curation-map", help="location of tissue curation map file",
        env_var="TISSUE_CURATION_MAP", action='store')
    p.add("--hpa-normal-tissue", help="location of tissue normal file",
        env_var="HPA_NORMAL_TISSUE_URL", action='store')
    p.add("--hpa-rna-level", help="location of rna level file",
        env_var="HPA_RNA_LEVEL_URL", action='store')
    p.add("--hpa-rna-value", help="location of rna value file",
        env_var="HPA_RNA_VALUE_URL", action='store')
    p.add("--hpa-rna-zscore", help="location of rna zscore file",
        env_var="HPA_RNA_ZSCORE_URL", action='store')

    #ontology URIs
    p.add("--ontology-efo", help="location of EFO file",
        env_var="ONTOLOGY_EFO", action='store')
    p.add("--ontology-hpo", help="location of HPO file",
        env_var="ONTOLOGY_HPO", action='store')
    p.add("--ontology-mp", help="location of MP file",
        env_var="ONTOLOGY_MP", action='store')
    p.add("--ontology-so", help="location of SO file",
        env_var="ONTOLOGY_SO", action='store')
    p.add("--ontology-eco", help="location of ECO file",
        env_var="ONTOLOGY_ECO", action='store')

    #disease-phenotype links
    p.add("--disease-phenotype", help="location of disese phenotype file(s)",
        env_var="DISEASE_PHENOTYPE", action='append')

    #eco score modifiers
    p.add("--eco-scores", help="location of ECO score modifiers file",
        env_var="ECO_SCORES", action='store')

    #chembl API
    p.add("--chembl-target", help="Chembl target by Uniprot ID file location",
        env_var="CHEMBL_TARGET", action='store')
    p.add("--chembl-mechanism", help="Chembl mechanism file location",
        env_var="CHEMBL_MECHANISM", action='store')
    p.add("--chembl-protein", help="Chembl protein file location",
        env_var="CHEMBL_PROTEIN", action='store')
    p.add("--chembl-component", help="Chembl component file location",
        env_var="CHEMBL_COMPONENT", action='store')
    p.add("--chembl-molecule-set-uri-pattern", help="Chembl molecule set uri pattern",
        env_var="CHEMBL_MOLECULE_SET_URI_PATTERN", action='store')



    return p

def get_args():
    p = configargparse.get_argument_parser()
    #dont use parse_args because that will error
    #if there are extra arguments e.g. for plugins
    args = p.parse_known_args()[0]

    #output all configuration values, useful for debugging
    p.print_values()

    # check legacy environment variables for backwards compatibility
    # note these will not be documented via --help !

#        if not args.redis_host and not args.redis_port and 'CTTV_REDIS_SERVER' in os.environ:
#            args.redis_host, args.redis_port = os.environ['CTTV_REDIS_REMOTE'].split(":")

#    if args.redis_remote:
#        Config.REDISLITE_REMOTE = args.redis_remote

#    if args.redis_host:
#        Config.REDISLITE_DB_HOST = args.redis_host

#    if args.redis_port:
#        Config.REDISLITE_DB_PORT = args.redis_port


    return args
