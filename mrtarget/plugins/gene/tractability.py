import logging
from yapsy.IPlugin import IPlugin
from mrtarget.Settings import Config
from mrtarget.common import URLZSource
from mrtarget.common.safercast import SaferBool, SaferFloat, SaferInt
from tqdm import tqdm
from itertools import compress
import csv


tractability_columns = ("id",
                        "ensembl_gene_id",
                        "accession",
                        "Bucket_1", "Bucket_2", "Bucket_3", "Bucket_4", "Bucket_5",
                        "Bucket_6", "Bucket_7", "Bucket_8", "Bucket_sum",
                        "Top_bucket",
                        "Category",
                        "Clinical_Precedence",
                        "Discovery_Precedence",
                        "Predicted_Tractable",
                        "ensemble",
                        "High_Quality_ChEMBL_compounds",
                        "Small_Molecule_Druggable_Genome_Member",
                        "Bucket_1_ab", "Bucket_2_ab", "Bucket_3_ab", "Bucket_4_ab", "Bucket_5_ab",
                        "Bucket_6_ab", "Bucket_7_ab", "Bucket_8_ab",
                        "Bucket_9_ab", "Bucket_sum_ab", "Top_bucket_ab", "Uniprot_high_conf_loc", "GO_high_conf_loc",
                        "Uniprot_med_conf_loc",
                        "GO_med_conf_loc", "Transmembrane", "Signal_peptide", "HPA_main_location",
                        "Clinical_Precedence_ab",
                        "Predicted_Tractable__High_confidence",
                        "Predicted_Tractable__Medium_to_low_confidence", "Category_ab")


class Tractability(IPlugin):
    # Initiate Tractability object
    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.loader = None
        self.r_server = None
        self.esquery = None
        self.ensembl_current = {}
        self.symbols = {}
        self.tractability = {}
        self.tqdm_out = None

    def print_name(self):
        self._logger.info("Tractability plugin")

    def merge_data(self, genes, loader, r_server, tqdm_out):

        self.loader = loader
        self.r_server = r_server
        self.tqdm_out = tqdm_out

        try:
            # Parse tractability data into self.tractability
            self.build_json(filename=Config.TRACTABILITY_FILENAME)

            # Iterate through all genes and add tractability data if gene symbol is present
            self._logger.info("Tractability data injection")

            for gene_id, gene in genes.iterate():
                if gene_id in self.tractability:
                    gene.tractability = self.tractability[gene_id]

        except Exception as ex:
            self._logger.exception(str(ex), exc_info=1)
            raise ex

    def build_json(self, filename):
        self._logger.info("data from TSV file comes in non standard ways, by ex. bool comes as a categ. data Y/N"
                          "so casting to bool, int and float with default fallback values instead of "
                          "throwing exceptions as we are parsing a TSV file where types are inexistent")
        to_bool = SaferBool(with_fallback=False)
        to_int = SaferInt(with_fallback=0)
        to_float = SaferFloat(with_fallback=0.)

        sm_bucket_list = [1, 2, 3, 4, 5, 6, 7, 8]
        ab_bucket_list = [1, 2, 3, 4, 5, 6, 7, 8, 9]

        with URLZSource(filename).open() as r_file:
            for i, el in enumerate(csv.DictReader(r_file, fieldnames=tractability_columns, delimiter='\t'), start=1):
                try:
                    # Get lists of small molecule and antibody buckets
                    buckets = list(el[k] for k in
                                   ("Bucket_1", "Bucket_2", "Bucket_3", "Bucket_4", "Bucket_5", "Bucket_6", "Bucket_7",
                                    "Bucket_8"))
                    buckets_ab = list(el[k] for k in
                                      ("Bucket_1_ab", "Bucket_2_ab", "Bucket_3_ab", "Bucket_4_ab", "Bucket_5_ab",
                                       "Bucket_6_ab", "Bucket_7_ab", "Bucket_8_ab", "Bucket_9_ab"))
                    sm_buckets = list(compress(sm_bucket_list, [x == '1' for x in buckets]))
                    ab_buckets = list(compress(ab_bucket_list, [x == '1' for x in buckets_ab]))

                    # struct is built inline as the most pythonic way is preferable and more explicit
                    #
                    line = {
                        'smallmolecule': {
                            'buckets': sm_buckets,  # list of buckets
                            'categories': {
                                'clinical_precedence': to_float(el["Clinical_Precedence"]),
                                'discovery_precedence': to_float(el["Discovery_Precedence"]),
                                'predicted_tractable': to_float(el["Predicted_Tractable"])
                            },
                            'top_category': el["Category"],
                            # TODO drugebility score not used at the moment but in a future
                            'ensemble': to_float(el["ensemble"]),
                            'high_quality_compounds':
                                to_int(el["High_Quality_ChEMBL_compounds"]),
                            'small_molecule_genome_member':
                                to_bool(el["Small_Molecule_Druggable_Genome_Member"])
                        },
                        'antibody': {
                            'buckets': ab_buckets,
                            'categories': {
                                'clinical_precedence':
                                    to_float(el["Clinical_Precedence_ab"]),
                                'predicted_tractable_high_confidence':
                                    to_float(el["Predicted_Tractable__High_confidence"]),
                                'predicted_tractable_med_low_confidence':
                                    to_float(el["Predicted_Tractable__Medium_to_low_confidence"])
                            },
                            'top_category': el["Category_ab"]
                        }
                    }

                    # Add data for current gene to self.tractability
                    self.tractability[el["ensembl_gene_id"]] = line

                except Exception as k_ex:
                    self._logger.exception("this line %d won't be inserted %s with ex: %s",
                                           i, str(el), str(k_ex))
