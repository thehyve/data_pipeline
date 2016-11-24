from collections import Counter

import collections
import jsonpickle
from elasticsearch import helpers

from common.DataStructure import SparseFloatDict
from common.ElasticsearchLoader import Loader
from settings import Config
import json

class AssociationSummary(object):

    def __init__(self, res):
        self.top_associations = dict(total = [], direct =[])
        self.associations_count = dict(total = 0, direct =0)
        if res['hits']['total']:
            self.associations_count['total'] = res['hits']['total']
            for hit in res['hits']['hits']:
                if '_source' in hit:
                    self.top_associations['total'].append(hit['_source'])
                elif 'fields' in hit:
                    self.top_associations['total'].append(hit['fields'])
            self.associations_count['direct'] = res['aggregations']['direct_associations']['doc_count']
            for hit in res['aggregations']['direct_associations']['top_direct_ass']['hits']['hits']:
                if '_source' in hit:
                    self.top_associations['direct'].append(hit['_source'])
                elif 'fields' in hit:
                    self.top_associations['direct'].append(hit['fields'])





class ESQuery(object):

    def __init__(self, es, dry_run = False):
        self.handler = es
        self.dry_run = dry_run

    @staticmethod
    def _get_source_from_fields(fields = None):
        if fields is None:
            fields = ['*']
        source = {"include": fields}
        return source

    def get_all_targets(self, fields = None):
        source = self._get_source_from_fields(fields)
        res = helpers.scan(client=self.handler,
                            query={"query": {
                                      "match_all": {}
                                    },
                                   '_source': source,
                                   'size': 20,
                                   },
                            scroll='12h',
                            doc_type=Config.ELASTICSEARCH_GENE_NAME_DOC_NAME,
                            index=Loader.get_versioned_index(Config.ELASTICSEARCH_GENE_NAME_INDEX_NAME),
                            timeout="30m",
                            )
        for hit in res:
            yield hit['_source']

    def get_targets_by_id(self, ids, fields = None):
        if not isinstance(ids, list):
            ids = [ids]

        source = self._get_source_from_fields(fields)
        res = helpers.scan(client=self.handler,
                            query={"query": {
                                            "ids" : {
                                                "values" : ids
                                              }
                                          },
                                          '_source': source,
                                          'size': 20,
                                      },
                            scroll='12h',
                            doc_type=Config.ELASTICSEARCH_GENE_NAME_DOC_NAME,
                            index=Loader.get_versioned_index(Config.ELASTICSEARCH_GENE_NAME_INDEX_NAME),
                            timeout="30m",
                            )
        for hit in res:
            yield hit['_source']
    
    def count_all_targets(self):

        return self.count_elements_in_index(Config.ELASTICSEARCH_GENE_NAME_INDEX_NAME)

    def get_all_diseases(self, fields = None):
        source = self._get_source_from_fields(fields)

        res = helpers.scan(client=self.handler,
                            query={"query": {
                                      "match_all": {}
                                    },
                                   '_source': source,
                                   'size': 1000,
                                   },
                            scroll='12h',
                            doc_type=Config.ELASTICSEARCH_EFO_LABEL_DOC_NAME,
                            index=Loader.get_versioned_index(Config.ELASTICSEARCH_EFO_LABEL_INDEX_NAME),
                            timeout="10m",
                            )
        for hit in res:
            yield hit['_source']

    def count_all_diseases(self):

        return self.count_elements_in_index(Config.ELASTICSEARCH_EFO_LABEL_INDEX_NAME)


    def get_all_eco(self, fields=None):
        source = self._get_source_from_fields(fields)

        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "match_all": {}
                           },
                               '_source': source,
                               'size': 1000,
                           },
                           scroll='2h',
                           doc_type=Config.ELASTICSEARCH_ECO_DOC_NAME,
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_ECO_INDEX_NAME),
                           timeout="10m",
                           )
        for hit in res:
            yield hit['_source']

    def count_all_eco(self):

        return self.count_elements_in_index(Config.ELASTICSEARCH_ECO_INDEX_NAME)

    def get_publications_with_analyzed_data(self,ids, fields=None):
        source = self._get_source_from_fields(fields)
        # inner hits to get child documents containing abstract_lemmas , along with parent publications
        res = helpers.scan(client=self.handler,
                           query={"query": {
                                     "has_child": {
                                        "type": "publication-analysis-spacy",
                                            "query": {
                                                        "ids": {"values": ids}

                                                    },"inner_hits": {}
                                        }
                                     },

                               '_source': source,
                               'size': 1000
                           },
                           scroll='2h',
                           doc_type=Config.ELASTICSEARCH_PUBLICATION_DOC_NAME,
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_PUBLICATION_INDEX_NAME),
                           timeout="10m",
                           )
        for hit in res:
            parent_publication = hit['_source']
            analyzed_publication = hit['inner_hits']['publication-analysis-spacy']['hits']['hits'][0]['_source']
            yield parent_publication, analyzed_publication

    def count_all_publications(self):

        return self.count_elements_in_index(Config.ELASTICSEARCH_PUBLICATION_INDEX_NAME)

    def get_associations_for_target(self, target, fields = None, size = 100, get_top_hits = True):
        source = self._get_source_from_fields(fields)
        aggs ={}
        if get_top_hits:
            aggs = {
                       "direct_associations": {
                           "filter": {"term": {"is_direct": True}},
                           'aggs': {
                               "top_direct_ass": {
                                   "top_hits": {
                                       "sort": {"harmonic-sum.overall": {"order": "desc"}},
                                       "_source": source,

                                       "size": size
                                   },
                               }
                           },
                       }
                   }

        res = self.handler.search(index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_ASSOCIATION_INDEX_NAME),
                                  doc_type=Config.ELASTICSEARCH_DATA_ASSOCIATION_DOC_NAME,
                                  body={"query": {
                                          "filtered": {
                                              "filter": {
                                                   "terms": {"target.id": [target]}
                                              }
                                          }
                                        },
                                       "sort" : { "harmonic-sum.overall" : {"order":"desc" }},
                                       '_source': source,
                                       "aggs" : aggs,
                                       'size': size,
                                       }
                                  )
        return AssociationSummary(res)

    def get_associations_for_disease(self, disease, fields = None, size = 100, get_top_hits = True):
        source = self._get_source_from_fields(fields)
        aggs = {}
        if get_top_hits:
            aggs = {
                "direct_associations": {
                    "filter": {"term": {"is_direct": True}},
                    'aggs': {
                        "top_direct_ass": {
                            "top_hits": {
                                "sort": {"harmonic-sum.overall": {"order": "desc"}},
                                "_source": source,

                                "size": size
                            },
                        }
                    },
                }
            }

        res = self.handler.search(index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_ASSOCIATION_INDEX_NAME),
                                  doc_type=Config.ELASTICSEARCH_DATA_ASSOCIATION_DOC_NAME,
                                  body={"query": {
                                          "filtered": {
                                              "filter": {
                                                   "terms": {"disease.id": [disease]}
                                              }
                                          }
                                        },
                                       "sort" : { "harmonic-sum.overall" : {"order":"desc"}},
                                       '_source': source,
                                       "aggs" : aggs,
                                       'size': size,
                                       }
                                  )
        return AssociationSummary(res)


    def get_validated_evidence_strings(self,  size=1000, datasources = []):



        # https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-multi-get.html
        index_name = Loader.get_versioned_index(Config.ELASTICSEARCH_VALIDATED_DATA_INDEX_NAME+'*')
        doc_type = None

        if datasources:
            doc_type = datasources
        res = helpers.scan(client=self.handler,
                           query={"query":  {"match_all": {}},
                               '_source': True,
                               'size': size,
                           },
                           scroll='12h',
                           doc_type=doc_type,
                           index=index_name,
                           timeout="10m",
                           )

        # res = list(res)
        for hit in res:
            yield hit['_source']

    def count_validated_evidence_strings(self, datasources = []):

        doc_type = None
        if datasources:
            doc_type = datasources

        return self.count_elements_in_index(Config.ELASTICSEARCH_VALIDATED_DATA_INDEX_NAME + '*',
                                            doc_type = doc_type)


    def get_all_ensembl_genes(self):
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "match_all": {}
                           },
                               '_source': True,
                               'size': 1000,
                           },
                           scroll='1h',
                           # doc_type=Config.ELASTICSEARCH_VALIDATED_DATA_DOC_NAME,
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_ENSEMBL_INDEX_NAME),
                           timeout="10m",
                           )
        for hit in res:
            yield hit['_source']

    def get_all_uniprot_entries(self):
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "match_all": {}
                           },
                               '_source': True,
                               'size': 100,
                           },
                           scroll='12h',
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_UNIPROT_INDEX_NAME),
                           timeout="10m",
                           )
        for hit in res:
            yield jsonpickle.loads(hit['_source']['entry'])


    def get_reaction(self, reaction_id):
        res = self.handler.search(index=Loader.get_versioned_index(Config.ELASTICSEARCH_REACTOME_INDEX_NAME),
                                  doc_type=Config.ELASTICSEARCH_REACTOME_REACTION_DOC_NAME,
                                  body={"query": {
                                            "ids" : {
                                                "values" : [reaction_id]
                                              }
                                          },
                                          '_source': True,
                                          'size': 1,
                                      }
                                  )
        for hit in res['hits']['hits']:
            return hit['_source']

    @property
    def get_disease_to_targets_vectors(self):
        #TODO: look at the multiquery api

        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "term": {
                                   "is_direct": True,
                               }
                           },
                               '_source': {'include':["target.id", 'disease.id', 'harmonic-sum.overall']},
                               'size': 1000,
                           },
                           scroll='12h',
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_ASSOCIATION_INDEX_NAME),
                           timeout="10m",
                           )

        target_results = dict()
        disease_results = dict()

        c=0
        for hit in res:
            c+=1
            hit = hit['_source']
            '''store target associations'''
            if hit['target']['id'] not in target_results:
                target_results[hit['target']['id']] = SparseFloatDict()
            target_results[hit['target']['id']][hit['disease']['id']]=hit['harmonic-sum']['overall']

            '''store disease associations'''
            if hit['disease']['id'] not in disease_results:
                disease_results[hit['disease']['id']] = SparseFloatDict()
            disease_results[hit['disease']['id']][hit['target']['id']] = hit['harmonic-sum']['overall']

            if c%10000 ==0:
                print c

        return target_results, disease_results

    def get_target_labels(self, ids):
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "ids": {
                                   "values": ids,
                               }
                           },
                               '_source': 'approved_symbol',
                               'size': 1,
                           },
                          scroll='12h',
                          index=Loader.get_versioned_index(Config.ELASTICSEARCH_GENE_NAME_INDEX_NAME),
                          timeout="10m",
                          )



        return dict((hit['_id'],hit['_source']['approved_symbol']) for hit in res)

    def get_disease_labels(self, ids):
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "ids": {
                                   "values": ids,
                               }
                           },
                               '_source': 'label',
                               'size': 1,
                           },
                           scroll='12h',
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_EFO_LABEL_INDEX_NAME),
                           timeout="10m",
                           )

        return dict((hit['_id'],hit['_source']['label']) for hit in res)

    def count_elements_in_index(self, index_name, doc_type=None):
        res = self.handler.search(index=Loader.get_versioned_index(index_name),
                                  doc_type=doc_type,
                                  body={"query": {
                                      "match_all": {}
                                  },
                                      '_source': False,
                                      'size': 0,
                                  }
                                  )
        return res['hits']['total']

    def get_evidence_simple(self, targets = None):

        def get_ids(ids):
            return self.handler.mget(index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME + '*'),
                                   body={'docs': ids},
                                   _source= {"include": ["target.id",
                                                        "private.efo_codes",
                                                        "disease.id",
                                                        "scores.association_score",
                                                        "sourceID",
                                                        "id",
                                                        ],
                                            })

        if targets is None:
            targets = self.get_all_target_ids_with_evidence_data()


        for target in targets:
            query_body = {
                "query": { "filtered": {
                                       "filter": {
                                           "terms": {"target.id": target}
                                       }
                                   }},
                '_source':  {"include": ["target.id",
                                        "disease.id",
                            ]},
                "sort": ["target.id", "disease.id"],
            }

            res = helpers.scan(client=self.handler,
                               query=query_body,
                               scroll='1h',
                               index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME + '*'),
                               timeout="1h",
                               request_timeout=2 * 60 * 60,
                               size=5000,
                               preserve_order=True
                               )
            ids = []
            for hit in res:
                ids.append({"_index": hit["_index"],
                                "_id" : hit["_id"]
                                },)
            id_buffer = []
            for doc_id in ids:
                id_buffer.append(doc_id)
                if len(id_buffer) == 1000:
                    res_get = get_ids(id_buffer)
                    for doc in res_get['docs']:
                        if doc['found']:
                            yield doc['_source']
                        else:
                            raise ValueError('document with id %s not found'%(doc['_id']))
                    id_buffer = []
            if id_buffer:
                res_get = get_ids(id_buffer)
                for doc in res_get['docs']:
                    if doc['found']:
                        yield doc['_source']
                    else:
                        raise ValueError('document with id %s not found' % (doc['_id']))


    def get_all_target_ids_with_evidence_data(self):
        #TODO: use an aggregation to get those with just data
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "match_all": {}
                           },
                               '_source': False,
                               'size': 100,
                           },
                           scroll='12h',
                           doc_type=Config.ELASTICSEARCH_GENE_NAME_DOC_NAME,
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_GENE_NAME_INDEX_NAME),
                           timeout="30m",
                           )
        for target in res:
            yield  target['_id']


    def get_evidence_for_target_simple(self, target, expected = None):
        query_body = {"query": {
                                "bool": {
                                  "filter": {
                                    "term": {
                                      "target.id": target
                                    }
                                  }
                                }
                            },
            '_source': {"include": ["target.id",
                                    "private.efo_codes",
                                    "disease.id",
                                    "scores.association_score",
                                    "sourceID",
                                    "id",
                                    ]},
            }

        if expected is not None and expected <10000:
            query_body['size']=10000
            res = self.handler.search(index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME + '*'),
                                      body=query_body,
                                      routing=target,
                                      )
            for hit in res['hits']['hits']:
                yield hit['_source']
        else:
            res = helpers.scan(client=self.handler,
                               query=query_body,
                               scroll='1h',
                               index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME + '*'),
                               timeout="1h",
                               request_timeout=2 * 60 * 60,
                               size=1000,
                               routing=target,
                               )
            for hit in res:
                yield hit['_source']

    def count_evidence_for_target(self, target):
        res = self.handler.search(index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME + '*'),
                                  body={
                                        "query": {
                                            "bool": {
                                              "filter": {
                                                "term": {
                                                  "target.id": target
                                                }
                                              }
                                            }
                                        },
                                        '_source': False,
                                        'size': 0,
                                    },
                                  routing=target,
                                  )
        return res['hits']['total']


    def get_publications_by_id(self, ids):
        query_body = {"query": {
                               "ids": {
                                   "values": ids,
                               }
                           },
                               '_source': True,
                               'size': 100,
                           }
        if len(ids) <10000:
            query_body['size']=10000
            res = self.handler.search(index=Loader.get_versioned_index(Config.ELASTICSEARCH_PUBLICATION_INDEX_NAME),
                                      doc_type = Config.ELASTICSEARCH_PUBLICATION_DOC_NAME,
                                      body=query_body,
                                      )
            for hit in res['hits']['hits']:
                yield hit['_source']
        else:
            res = helpers.scan(client=self.handler,
                               query=query_body,
                               scroll='12h',
                               index=Loader.get_versioned_index(Config.ELASTICSEARCH_PUBLICATION_INDEX_NAME),
                               doc_type=Config.ELASTICSEARCH_PUBLICATION_DOC_NAME,
                               timeout="10m",
                               )
            for hit in res:
                yield hit['_source']


    def get_all_pub_ids_from_validated_evidence(self, datasources= None):
        for i,hit in enumerate(self.get_validated_evidence_strings(#fields='evidence_string.literature.references.lit_id',
                                                                    size=10000,
                                                   datasources=datasources)):
            if hit:
                try:
                    ev = json.loads(hit['evidence_string'])
                    for lit in ev['literature']['references']:
                        yield lit['lit_id'].split('/')[-1]
                except KeyError:
                    pass


    def get_all_pub_from_validated_evidence(self,datasources= None, batch_size=1000):
        batch = []
        for i,hit in enumerate(self.get_validated_evidence_strings(#fields='evidence_string.literature.references.lit_id',
                                                                    size=batch_size,
                                                   datasources=datasources)):
            if hit:
                try:
                    ev = json.loads(hit['evidence_string'])
                    for lit in ev['literature']['references']:
                        batch.append(lit['lit_id'].split('/')[-1])
                except KeyError:
                    pass
            if len(batch)>=batch_size:
                for pub in self.get_publications_by_id(batch):
                    yield pub
                batch =[]
        if batch:
            for pub in self.get_publications_by_id(batch):
                yield pub

    def get_all_associations_ids(self,):
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "match_all": {}
                           },
                               '_source': False,
                               'size': 1000,
                           },
                           scroll='1h',
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_ASSOCIATION_INDEX_NAME),
                           timeout="10m",
                           )
        for hit in res:
            yield hit['_id']

    def get_all_associations(self,):
        res = helpers.scan(client=self.handler,
                           query={"query": {
                               "match_all": {}
                           },
                               '_source': True,
                               'size': 1000,
                           },
                           scroll='1h',
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_ASSOCIATION_INDEX_NAME),
                           timeout="10m",
                           )
        for hit in res:
            yield hit['_source']

    def get_all_target_disease_pair_from_evidence(self, only_direct=False):

        res = helpers.scan(client=self.handler,
                           query={"query": {
                                    "match_all": {}
                                    },
                                 '_source': self._get_source_from_fields(['target.id', 'disease.id', 'private.efo_codes','scores.association_score']),
                                 'size': 1000,
                                 },
                           scroll='6h',
                           index=Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME + '*'),
                           timeout="1h",
                           request_timeout=2 * 60 * 60,
                           )

        for hit in res:
            if hit['_source']['scores']['association_score']>0:
                if only_direct:
                    yield '-'.join([hit['_source']['target']['id'],hit['_source']['disease']['id']])
                else:
                    for efo_id in hit['_source']['private']['efo_codes']:
                        yield '-'.join([hit['_source']['target']['id'],efo_id])

    def count_evidence_sourceIDs(self, target, disease):
        count = Counter()
        for ev_hit in helpers.scan(client=self.handler,
                                    query={"query": {
                                              "filtered": {
                                                  "filter": {
                                                      "bool": {
                                                          "must": [
                                                              {"terms": {"target.id": [target]}},
                                                              {"terms": {"private.efo_codes": [disease]}},
                                                                    ]
                                                      }
                                                  }
                                              }
                                            },
                                           '_source': dict(include=['sourceID']),
                                           'size': 1000,
                                    },
                                    scroll = '1h',
                                    index = Loader.get_versioned_index(Config.ELASTICSEARCH_DATA_INDEX_NAME+'*'),
                                    timeout = '1h',
                                    ):
            count [ev_hit['_source']['sourceID']]+=1

        return count

    def delete_data(self, index, query, doc_type = '', chunk_size=1000, altered_keys=()):
        '''
        Delete all the documents in an index matching a given query
        :param index: index to use
        :param query: query matching the elements to remove
        :param doc_type: document types, default is to look for all the doc types
        :param chunk_size: size of the bulk action sent to delete
        :param altered_keys: list of fields to fetch data and return as being altered by the delete query
        :return: dict of keys altered by the query
        '''

        '''count available data'''
        res = self.handler.search(index=Loader.get_versioned_index(index),
                                  body={
                                      "query": query,
                                      '_source': False,
                                      'size': 0,
                                  },
                                  doc_type = doc_type,
                                  )
        total = res['hits']['total']
        '''if data is matching query, delete it with scan and bulk'''
        altered = dict()
        for key in altered_keys:
            altered[key]=set()
        if total:
            batch = []
            for hit in helpers.scan(client=self.handler,
                                    query={"query": query,
                                       '_source': self._get_source_from_fields(altered_keys),
                                       'size': chunk_size,
                                    },
                                    scroll='1h',
                                    index=Loader.get_versioned_index(index),
                                    doc_type=doc_type,
                                    timeout='1h',
                                       ):
                action = {
                    '_op_type': 'delete',
                    '_index': hit['_index'],
                    '_type': hit['_type'],
                    '_id': hit['_id'],
                }
                if '_routing' in hit:
                    action['_routing'] = hit['_routing']
                batch.append(action)
                flat_source = self.flatten(hit['_source'])
                for key in altered_keys:
                    if key in flat_source:
                        altered[key].add(flat_source[key])
                if len(batch)>= chunk_size:
                    self._flush_bulk(batch)
                    batch = []

            if len(batch) >= chunk_size:
                self._flush_bulk(batch)
            '''flush changes'''
            self.handler.indices.flush(Loader.get_versioned_index(index),
                             wait_if_ongoing=True)

        return altered

    def delete_evidence_for_datasources(self, datasources):
        '''
        delete all the evidence objects with a given source id
        :param sourceID: a list of datasources ids to delete
        :return:
        '''

        if not isinstance(datasources, (list, tuple)):
            datasources = [datasources]
        query = {
            "filtered": {
                "filter": {
                    "terms": {"sourceID": datasources},
                    }
                }
            }
        self.delete_data(Config.ELASTICSEARCH_DATA_INDEX_NAME+'*',
                         query=query)

    def _flush_bulk(self, batch):
        if not self.dry_run:
            return helpers.bulk(self.handler,
                                batch,
                                stats_only=True)

    @staticmethod
    def flatten(d, parent_key='', separator='.'):
        '''
        takes a nested dictionary as input and generate a flat one with keys separated by the separator
        :param d: dictionary
        :param parent_key: a prefix for all flattened keys
        :param separator: separator between nested keys
        :return: flattened dictionary
        '''
        flat_fields = []
        for k, v in d.items():
            flat_key = parent_key + separator + k if parent_key else k
            if isinstance(v, collections.MutableMapping):
                flat_fields.extend(ESQuery.flatten(v, flat_key, separator=separator).items())
            else:
                flat_fields.append((flat_key, v))
        return dict(flat_fields)