import scrapy
from ..items import QuestionListItem
from datetime import datetime
from elasticsearch import Elasticsearch
import tensorflow as tf
import tensorflow_hub as hub

es = Elasticsearch([{'host': 'localhost', 'port': 9200}])
if es.ping():
    print('Connected to ES!')
else:
    print('Could not connect!')


structure = {
    "settings": {
            "analysis": {
                "filter": {
                "autocomplete_filter": {
                "type": "edge_ngram",
                "min_gram": 1,
                "max_gram": 5
                }
            },
                "analyzer": {
                    "autocomplete_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [ "lowercase", "autocomplete_filter"]
                }
            }
        }
    },    
    "mappings": {
        "properties": {
            "answers": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "details": {
                "type": "text",
                # "enabled": false,
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "question": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                },
                "analyzer": "autocomplete_analyzer"
            },
            "tags": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "upvotes": {
                "type": "text",
                # "enabled": false,
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "total_vectors": {
                "type": "dense_vector",
                # "enabled": false,
                "dims": 512
            }
        }

    }
}
res = es.indices.create(index='ie-3', ignore=400, body=structure)

embed = hub.load('universal_encoder')


def make_vector(query):
    embeddings = embed([query])
    vector = []
    for i in embeddings[0]:
        vector.append(float(i))
    return vector


class stackoverflow(scrapy.Spider):
    i = 0
    page_no = 1
    name = 'stackoverflow'
    start_urls = [
        "https://stackoverflow.com/questions?sort=MostVotes&edited=true&page={}".format(
            page_no)
    ]

    def parse(self, response):
        base_url = 'https://stackoverflow.com'
        que_set = response.css('div.question-summary')
        for q in que_set:
            self.i += 1
            link = q.css('h3 a::attr(href)').get()
            # print(link)
            yield response.follow(url=base_url + link, callback=self.parse_question)
        # if self.page_no<50:
        self.page_no += 1
        yield scrapy.Request(url="https://stackoverflow.com/questions?sort=MostVotes&edited=true&page={}".format(self.page_no), callback=self.parse)

    def parse_question(self, response):
        items = QuestionListItem()
        data = response.css('div.inner-content')
        items['question'] = data.css(
            "div h1 a.question-hyperlink::text").extract_first()
        details = data.css("div.question div.s-prose").extract()
        answers_raw = data.css('#answers')
        tags = response.css('a.post-tag::text').extract()
        tags_set = set(tags)
        tags = list(tags_set)
        upvotes =  response.css("div.js-vote-count::text").extract_first()
        if answers_raw:
            answers = ''
            raw_data = answers_raw.css("div.s-prose").extract_first()
            for row in raw_data:
                answers = answers + row  # put a newline if newline separated data is needed

        concat_details = ''
        for detail in details:
            # put a newline if newline separated data is needed
            concat_details = concat_details + detail
        items['details'] = concat_details
        items['answers'] = answers
        items['upvotes'] = upvotes
        items['tags'] = tags
        items['total_vectors'] = make_vector(items['question'])
        doc = {
            'question': items['question'],
            'details': items['details'],
            'answers': items['answers'],
            'tags': items['tags'],
            'upvotes':items['upvotes'],
            'total_vectors': items['total_vectors']
        }
        res = es.index(index="ie-3", body=doc)
        print(res['result'])

        yield items



